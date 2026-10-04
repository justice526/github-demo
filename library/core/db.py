"""连接管理与事务边界

原项目里 9 个业务模块共 95 处直接调用 `get_conn()`，每次自己开连接、
自己 commit —— 没有统一入口，也没有事务边界。本模块把这件事收拢。

提供两种用法：

1) 简单查询（自动提交、连接归还）
       with core.db.cursor() as cur:
           cur.execute("SELECT ...")
           rows = cur.fetchall()

2) 多步写入（显式事务，异常自动回滚）
       with core.db.transaction() as cur:
           cur.execute("UPDATE ...")
           cur.execute("INSERT ...")
       # 离开 with 且无异常即提交

设计约束：
- 只用标准库 sqlite3，零第三方依赖
- SQLite 的连接不能跨线程共享，故池按线程隔离（threading.local）
- 保留对旧 `db.get_conn()` 的兼容，供未重构完的模块继续使用

关于 WAL 模式：曾尝试开启 `PRAGMA journal_mode = WAL` 以提升并发，
但它会改写数据库文件头，导致 library.db 在 git 中始终显示为已修改，
与"提交干净数据库快照"的项目约定冲突。本项目是单用户桌面程序、
并发极低，WAL 收益有限，故**不启用**，保持默认的 delete 日志模式。
"""

import os
import sqlite3
import threading
from contextlib import contextmanager

from .errors import DatabaseError

# 数据库文件与项目根目录同级
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "library.db")

# 每个线程独立持有一个连接，避免跨线程复用导致的事务混乱
_local = threading.local()
# 写操作串行化：SQLite 单写者模型，并发写会直接抛 database is locked
_write_lock = threading.RLock()


def get_db_path():
    """当前生效的数据库路径（便于测试时指向临时库）"""
    return getattr(_local, "db_path", None) or DB_PATH


def set_db_path(path):
    """切换数据库文件，测试专用；会自动关闭当前线程的旧连接"""
    close_connection()
    _local.db_path = path
    return path


def _create_connection(path):
    """建立一个配置好的连接

    - isolation_level=None 关闭 sqlite3 的隐式事务管理，事务由我们自己控制
    - row_factory 让查询结果可以按列名访问
    - foreign_keys 打开，保证跨表引用完整性
    """
    try:
        conn = sqlite3.connect(path, timeout=15.0, isolation_level=None)
    except sqlite3.Error as e:
        raise DatabaseError(f"无法连接数据库：{e}", detail=str(e)) from e
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_conn():
    """取得当前线程的连接（惰性创建）

    兼容旧代码：原来 `from db import get_conn` 的地方可以继续用。
    新代码请优先用 `cursor()` 或 `transaction()` 上下文管理器。
    """
    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn
    path = get_db_path()
    conn = _create_connection(path)
    _local.conn = conn
    return conn


def close_connection():
    """关闭当前线程持有的连接并从缓存中摘除"""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass
        _local.conn = None


@contextmanager
def cursor(commit=False):
    """游标上下文：用于单条或少量只读查询

    :param commit: 为 True 时退出前自动提交（写操作建议显式用 transaction）
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            _commit(conn)
    except sqlite3.Error as e:
        raise DatabaseError(f"数据库操作失败：{e}", detail=str(e)) from e
    finally:
        cur.close()


@contextmanager
def transaction():
    """事务上下文：多步写入必须用它，保证要么全成功要么全回滚

    用法::

        with transaction() as cur:
            cur.execute("UPDATE book SET is_borrow=1 WHERE id=?", (bid,))
            cur.execute("INSERT INTO borrow_record(...) VALUES(...)")

    嵌套调用是安全的：内层检测到已在事务中就直接复用外层游标，
    不会提前提交，也不会重复 BEGIN。
    """
    # 已在事务中（嵌套场景）→ 复用外层，不新开
    if getattr(_local, "in_transaction", False):
        cur = get_conn().cursor()
        try:
            yield cur
        finally:
            cur.close()
        return

    conn = get_conn()
    with _write_lock:
        cur = conn.cursor()
        _local.in_transaction = True
        try:
            cur.execute("BEGIN IMMEDIATE")
            yield cur
            conn.commit()
        except sqlite3.Error as e:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise DatabaseError(f"事务执行失败，已回滚：{e}", detail=str(e)) from e
        except Exception:
            # 业务异常也要回滚，否则前面的写入会留在库里
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise
        finally:
            _local.in_transaction = False
            cur.close()


def _commit(conn):
    """提交并做异常包装"""
    try:
        conn.commit()
    except sqlite3.Error as e:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise DatabaseError(f"提交失败：{e}", detail=str(e)) from e


def query_one(sql, params=()):
    """执行查询并返回首行（无结果返回 None）"""
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def query_all(sql, params=()):
    """执行查询并返回全部行"""
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql, params=()):
    """执行单条写语句并提交，返回受影响行数"""
    with cursor(commit=True) as cur:
        cur.execute(sql, params)
        return cur.rowcount


def table_exists(name):
    """判断表是否存在，用于各模块的幂等初始化与优雅降级"""
    with cursor() as cur:
        cur.execute("""SELECT COUNT(*) FROM sqlite_master
                       WHERE type = 'table' AND name = ?""", (name,))
        row = cur.fetchone()
        return bool(row and row[0])


def reset_all():
    """关闭所有线程的连接，仅测试用"""
    close_connection()
