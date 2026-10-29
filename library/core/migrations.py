"""数据库版本化迁移（零第三方依赖，仅标准库）

设计
----
- ``schema_migrations`` 表记录已应用版本：version 主键 + description + applied_at。
- 迁移按版本号（零填充字符串，字典序即数值序）顺序执行。
- 每个迁移在**独立事务**中执行并登记版本；失败整条回滚，绝不留下半成品。
- 每个迁移提供 ``up``（应用）与 ``down``（回滚），支持按版本回滚。
- 基线 ``0001`` 用 ``CREATE TABLE IF NOT EXISTS`` 复刻当前全部表，对既有库幂等：
  只登记版本，不重建表；对空库则一次性建全所有表。
- DDL 内联在本模块（迁移是某时刻 schema 的不可变快照），
  不从 ``repository`` 反向引用，保持 core 作为最底层的分层约束。

用法::

    from core import migrations
    migrations.apply_all()          # web.py 启动时调用（幂等）

    python -m core.migrations status                 # 查看版本状态
    python -m core.migrations apply                  # 应用所有未执行迁移
    python -m core.migrations rollback 0001          # 回滚到 0001 之后（即撤销 0001 以上的迁移）
    python -m core.migrations rollback ""            # 全部回滚（危险）
"""

import sys
from datetime import datetime

from core import db


class Migration(object):
    """一个版本迁移：版本号、说明、up/down 回调（接收事务游标）"""

    __slots__ = ("version", "description", "up", "down")

    def __init__(self, version, description, up, down):
        self.version = version
        self.description = description
        self.up = up
        self.down = down


def _run_sql(cur, statements):
    for sql in statements:
        cur.execute(sql)


# ---- 基线：当前全部 11 张表（与线上 schema 完全一致，IF NOT EXISTS 幂等）----
_BASELINE_DDL = [
    """CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        balance REAL DEFAULT 0,
        security_q TEXT,
        security_a TEXT,
        is_admin INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS book (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT,
        category TEXT,
        is_borrow INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS borrow_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        book_id INTEGER,
        borrow_time TEXT,
        return_deadline TEXT,
        return_time TEXT,
        penalty REAL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES user(id),
        FOREIGN KEY(book_id) REFERENCES book(id)
    )""",
    """CREATE TABLE IF NOT EXISTS rating (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        score REAL NOT NULL,
        comment TEXT DEFAULT '',
        create_time TEXT,
        UNIQUE(user_id, book_id)
    )""",
    """CREATE TABLE IF NOT EXISTS tag (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS book_tag (
        book_id INTEGER NOT NULL,
        tag_id INTEGER NOT NULL,
        PRIMARY KEY (book_id, tag_id)
    )""",
    """CREATE TABLE IF NOT EXISTS reservation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        reserve_time TEXT,
        status TEXT DEFAULT 'waiting',
        notify_time TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS refresh_token (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        created_at INTEGER NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS notification_read (
        user_id INTEGER NOT NULL,
        nkey TEXT NOT NULL,
        read_at TEXT NOT NULL,
        PRIMARY KEY (user_id, nkey)
    )""",
    """CREATE TABLE IF NOT EXISTS operation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        action TEXT,
        target TEXT,
        detail TEXT,
        log_time TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )""",
]

# 回滚基线：按依赖关系先子后父地删表
_BASELINE_DROP = [
    "DROP TABLE IF EXISTS book_tag",
    "DROP TABLE IF EXISTS rating",
    "DROP TABLE IF EXISTS reservation",
    "DROP TABLE IF EXISTS notification_read",
    "DROP TABLE IF EXISTS refresh_token",
    "DROP TABLE IF EXISTS operation_log",
    "DROP TABLE IF EXISTS config",
    "DROP TABLE IF EXISTS tag",
    "DROP TABLE IF EXISTS borrow_record",
    "DROP TABLE IF EXISTS book",
    "DROP TABLE IF EXISTS user",
]

# 借阅记录的两个常用查询维度建索引（"我的当前借阅" / 某书借阅历史）
_INDEX_UP = [
    "CREATE INDEX IF NOT EXISTS idx_borrow_user ON borrow_record(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_borrow_book ON borrow_record(book_id)",
]
_INDEX_DOWN = [
    "DROP INDEX IF EXISTS idx_borrow_user",
    "DROP INDEX IF EXISTS idx_borrow_book",
]


MIGRATIONS = [
    Migration("0001", "baseline: 11 tables (user/book/borrow/rating/tag/...)",
              lambda cur: _run_sql(cur, _BASELINE_DDL),
              lambda cur: _run_sql(cur, _BASELINE_DROP)),
    Migration("0002", "index borrow_record(user_id, book_id)",
              lambda cur: _run_sql(cur, _INDEX_UP),
              lambda cur: _run_sql(cur, _INDEX_DOWN)),
]

_BY_VERSION = {m.version: m for m in MIGRATIONS}


def _now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            description TEXT,
            applied_at  TEXT NOT NULL
        )""")


def _table_exists(conn):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    return row is not None


def applied_versions():
    """已应用版本集合（只读，不创建任何表）"""
    conn = db.get_conn()
    if not _table_exists(conn):
        return set()
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def status():
    """全部迁移及其应用状态（按版本升序）"""
    done = applied_versions()
    return [{"version": m.version, "description": m.description,
             "applied": m.version in done} for m in MIGRATIONS]


def apply_all():
    """按序应用所有未执行迁移，返回本次新应用的版本列表（幂等）。

    :raises DatabaseError: 任一迁移失败——该迁移整体回滚，已成功的保留
    """
    conn = db.get_conn()
    _ensure_table(conn)
    done = applied_versions()
    newly = []
    for m in MIGRATIONS:
        if m.version in done:
            continue
        with db.transaction() as cur:
            m.up(cur)
            cur.execute(
                "INSERT INTO schema_migrations(version, description, applied_at) "
                "VALUES (?, ?, ?)", (m.version, m.description, _now()))
        newly.append(m.version)
    return newly


def rollback_to(target_version=""):
    """回滚所有 version > target_version 的已应用迁移。

    :param target_version: 目标版本（保留到该版本）；空串表示全部回滚
    :return: 实际回滚的版本列表（倒序）
    :raises ValueError: 目标版本不存在
    """
    conn = db.get_conn()
    if not _table_exists(conn):
        return []  # 无迁移记录，无需回滚
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    if target_version and target_version not in _BY_VERSION:
        raise ValueError("未知目标版本：%s" % target_version)
    to_roll = [m.version for m in reversed(MIGRATIONS)
               if m.version in done
               and (not target_version or m.version > target_version)]
    rolled = []
    for v in to_roll:
        m = _BY_VERSION[v]
        with db.transaction() as cur:
            m.down(cur)
            cur.execute("DELETE FROM schema_migrations WHERE version = ?", (v,))
        rolled.append(v)
    return rolled


def _main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        for row in status():
            mark = "✓" if row["applied"] else "·"
            print("%s %s  %s" % (mark, row["version"], row["description"]))
    elif cmd == "apply":
        newly = apply_all()
        print("已应用：%s" % (", ".join(newly) if newly else "（无，均为最新）"))
    elif cmd == "rollback":
        target = argv[2] if len(argv) > 2 else ""
        rolled = rollback_to(target)
        print("已回滚：%s" % (", ".join(rolled) if rolled else "（无）"))
    else:
        print("用法：python -m core.migrations [status|apply|rollback <目标版本|''>]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
