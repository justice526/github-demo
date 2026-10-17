"""通知已读状态数据访问层

通知本身是**动态聚合**的（待取预约 / 即将到期 / 逾期未还），没有实体表。
但「已读」状态需要服务端持久化，否则刷新/重登录后未读红点会反复出现。

因此本表只记录「用户已读过的通知 key」，key 由通知聚合层稳定生成：
    ready:<reservation_id>   待取预约
    due:<record_id>          即将到期
    overdue:<record_id>      逾期未还
"""
from datetime import datetime

from core import db


def init_table():
    """幂等建表：用户级「已读 key」集合"""
    with db.transaction() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS notification_read (
            user_id  INTEGER NOT NULL,
            nkey     TEXT    NOT NULL,
            read_at  TEXT    NOT NULL,
            PRIMARY KEY (user_id, nkey)
        )""")


def is_read(user_id, key):
    """该 key 是否已被用户标记为已读"""
    row = db.query_one(
        "SELECT 1 FROM notification_read WHERE user_id = ? AND nkey = ?",
        (user_id, key))
    return row is not None


def mark_read(user_id, key):
    """标记单个 key 为已读（幂等 upsert）"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db.transaction() as cur:
        cur.execute(
            "INSERT OR REPLACE INTO notification_read(user_id, nkey, read_at) "
            "VALUES (?,?,?)", (user_id, key, now))


def mark_keys_read(user_id, keys):
    """批量标记多个 key 为已读"""
    if not keys:
        return 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [(user_id, k, now) for k in keys]
    with db.transaction() as cur:
        cur.executemany(
            "INSERT OR REPLACE INTO notification_read(user_id, nkey, read_at) "
            "VALUES (?,?,?)", rows)
    return len(rows)
