"""操作日志数据访问层

表归属：本模块独占 `operation_log` 表。

**重要设计**：写日志是「附加价值」，失败绝不能影响主业务。
本 repo 的 `insert()` 会被 service 层包在 try/except 中调用。
用户名通过 `user_repo.get_username()` 获取，日志模块自己不查 user 表。
"""

from datetime import datetime

from core import db


def _to_tuple(row):
    return tuple(row) if row is not None else None


def _to_tuples(rows):
    return [tuple(r) for r in rows]


def init_table():
    """幂等建表"""
    with db.transaction() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS operation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                action TEXT,
                target TEXT,
                detail TEXT,
                log_time TEXT
            )
        """)


def table_ready():
    return db.table_exists("operation_log")


# ==================== 写 ====================

def insert(user_id, username, action, target="", detail=""):
    """写入一条操作日志，返回日志 ID

    调用方必须自行捕获异常 —— 见 service.log_service。
    """
    with db.transaction() as cur:
        cur.execute("""
            INSERT INTO operation_log(user_id, username, action, target, detail, log_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, action, target, detail,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return cur.lastrowid


def clear_all():
    """清空全部日志，返回清空条数；表不存在时返回 0"""
    if not table_ready():
        return 0
    with db.transaction() as cur:
        cur.execute("DELETE FROM operation_log")
        return cur.rowcount


# ==================== 读 ====================

def find_logs(limit=100, action=None, user_id=None):
    """查询日志

    :param limit: 最多返回条数
    :param action: 按动作码过滤，None 表示全部
    :param user_id: 按用户过滤，None 表示全部
    :return: [(id, username, action, target, detail, log_time), ...]
    """
    if not table_ready():
        return []
    sql = """
        SELECT id, username, action, target, detail, log_time
        FROM operation_log WHERE 1=1
    """
    params = []
    if action:
        sql += " AND action = ?"
        params.append(action)
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return _to_tuples(db.query_all(sql, tuple(params)))


def action_stats():
    """各动作计数：[(action, cnt), ...]，按次数降序"""
    if not table_ready():
        return []
    return _to_tuples(db.query_all("""
        SELECT action, COUNT(*) AS cnt
        FROM operation_log
        GROUP BY action
        ORDER BY cnt DESC, action
    """))


def count_all():
    if not table_ready():
        return 0
    row = db.query_one("SELECT COUNT(*) FROM operation_log")
    return row[0] if row else 0
