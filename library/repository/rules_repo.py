"""规则参数数据访问层

表归属：本模块独占 `config` 表（key-value 通用参数表）。

拆分说明：旧 `get_borrow_summary()` 把 SQL 统计和业务计算
（limit / remaining / 阈值判断）混在一起。这里只负责取数，
计算逻辑上移到 service.rules_service。
"""

from core import db

# 默认参数（与旧 rules.py 保持一致）
DEFAULT_BORROW_LIMIT = 5
DEFAULT_FINE_THRESHOLD = 10


def _to_tuple(row):
    return tuple(row) if row is not None else None


def _to_tuples(rows):
    return [tuple(r) for r in rows]


def init_table():
    """幂等建表"""
    with db.transaction() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")


def table_ready():
    return db.table_exists("config")


# ==================== 参数读写 ====================

def get_value(key, default=None):
    """读取配置项；表不存在时返回 default（优雅降级）"""
    if not table_ready():
        return default
    row = db.query_one("SELECT value FROM config WHERE key = ?", (key,))
    return row[0] if row else default


def set_value(key, value):
    """写入配置项（存在则覆盖）"""
    with db.transaction() as cur:
        cur.execute("""
            INSERT INTO config(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
    return True


def all_values():
    """全部配置项：[(key, value), ...]"""
    if not table_ready():
        return []
    return _to_tuples(db.query_all("SELECT key, value FROM config ORDER BY key"))


# ==================== 借阅状态统计（只取数，不做业务计算）====================

def count_borrowed(user_id):
    """在借未还数量"""
    return db.query_one(
        "SELECT COUNT(*) FROM borrow_record WHERE user_id = ? AND return_time IS NULL",
        (user_id,))[0] or 0


def count_overdue(user_id):
    """逾期未还数量（用 SQLite 自己的时间比较，与旧实现一致）"""
    return db.query_one("""
        SELECT COUNT(*) FROM borrow_record
        WHERE user_id = ? AND return_time IS NULL
          AND return_deadline < datetime('now', 'localtime')
    """, (user_id,))[0] or 0


def sum_unpaid_fine(user_id):
    """未结清罚款总额"""
    return db.query_one(
        "SELECT SUM(penalty) FROM borrow_record WHERE user_id = ? AND penalty > 0",
        (user_id,))[0] or 0.0
