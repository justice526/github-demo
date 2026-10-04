"""预约数据访问层

表归属：本模块独占 `reservation` 表。

状态机：waiting（排队中） → ready（已到书待取） → done / cancelled

队列推进规则（业务逻辑属 service，此处只提供原语）：
- 归还图书时才把队首 waiting 提升为 ready
- 借走图书**不**推进队列（书仍在借出状态，预约无意义）
"""

from datetime import datetime

from core import db

STATUS_WAITING = "waiting"
STATUS_READY = "ready"
STATUS_DONE = "done"
STATUS_CANCELLED = "cancelled"


def _to_tuple(row):
    return tuple(row) if row is not None else None


def _to_tuples(rows):
    return [tuple(r) for r in rows]


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_table():
    """幂等建表"""
    with db.transaction() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reservation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                reserve_time TEXT,
                status TEXT DEFAULT 'waiting',
                notify_time TEXT,
                UNIQUE(user_id, book_id)
            )
        """)


def table_ready():
    return db.table_exists("reservation")


# ==================== 读 ====================

def find_one(user_id, book_id):
    """某用户对某书的预约记录，不存在返回 None

    同 borrow_repo.find_active_by_user_book：返回 Row 而非 tuple，
    调用方按列名取值，避免查询列增减时静默错位。
    """
    return db.query_one("""
        SELECT id, user_id, book_id, reserve_time, status, notify_time
        FROM reservation WHERE user_id = ? AND book_id = ?
    """, (user_id, book_id))


def find_by_user(user_id, active_only=True):
    """某用户的预约列表

    :param active_only: True 只返回 waiting/ready（未完成的）
    """
    sql = """
        SELECT r.id, b.title, r.reserve_time, r.status, r.notify_time
        FROM reservation r
        LEFT JOIN book b ON r.book_id = b.id
        WHERE r.user_id = ?
    """
    if active_only:
        sql += " AND r.status IN ('waiting', 'ready')"
    sql += " ORDER BY r.id DESC"
    return _to_tuples(db.query_all(sql, (user_id,)))


def queue_of(book_id):
    """某本书的预约队列（按预约时间先后）"""
    return _to_tuples(db.query_all("""
        SELECT r.id, r.user_id, u.username, r.reserve_time, r.status
        FROM reservation r
        LEFT JOIN user u ON r.user_id = u.id
        WHERE r.book_id = ? AND r.status IN ('waiting', 'ready')
        ORDER BY r.reserve_time, r.id
    """, (book_id,)))


def count_active(book_id):
    """某书的有效预约人数"""
    return db.query_one("""
        SELECT COUNT(*) FROM reservation
        WHERE book_id = ? AND status IN ('waiting', 'ready')
    """, (book_id,))[0] or 0


def count_waiting(book_id):
    """某书排队中的人数"""
    return db.query_one(
        "SELECT COUNT(*) FROM reservation WHERE book_id = ? AND status = 'waiting'",
        (book_id,))[0] or 0


def find_ready_for_user(user_id):
    """某用户所有「已到书待取」的预约"""
    return _to_tuples(db.query_all("""
        SELECT r.id, b.title, r.book_id, r.notify_time
        FROM reservation r
        LEFT JOIN book b ON r.book_id = b.id
        WHERE r.user_id = ? AND r.status = 'ready'
        ORDER BY r.notify_time DESC
    """, (user_id,)))


def get_status(user_id, book_id):
    """取某预约的状态，不存在返回 None"""
    row = db.query_one(
        "SELECT status FROM reservation WHERE user_id = ? AND book_id = ?",
        (user_id, book_id))
    return row[0] if row else None


def head_waiting(book_id):
    """取某书队首（最早预约且仍在排队的人），返回 (reservation_id, user_id)"""
    return _to_tuple(db.query_one("""
        SELECT id, user_id FROM reservation
        WHERE book_id = ? AND status = 'waiting'
        ORDER BY reserve_time, id LIMIT 1
    """, (book_id,)))


def ready_holder(book_id):
    """当前处于 ready 状态的预约人 user_id（用于优先取书权判定）"""
    row = db.query_one("""
        SELECT user_id FROM reservation
        WHERE book_id = ? AND status = 'ready'
        ORDER BY notify_time DESC LIMIT 1
    """, (book_id,))
    return row[0] if row else None


# ==================== 写 ====================

def insert(user_id, book_id, reserve_time=None, status=STATUS_WAITING):
    """新增预约，返回预约 ID"""
    with db.transaction() as cur:
        cur.execute("""
            INSERT INTO reservation(user_id, book_id, reserve_time, status, notify_time)
            VALUES (?, ?, ?, ?, NULL)
        """, (user_id, book_id, reserve_time or now_str(), status))
        return cur.lastrowid


def set_status(reservation_id, status, notify_time=None):
    """更新预约状态"""
    with db.transaction() as cur:
        if notify_time is not None:
            cur.execute("UPDATE reservation SET status = ?, notify_time = ? WHERE id = ?",
                        (status, notify_time, reservation_id))
        else:
            cur.execute("UPDATE reservation SET status = ? WHERE id = ?",
                        (status, reservation_id))
        return cur.rowcount


def set_status_in(cur, reservation_id, status, notify_time=None):
    """同 set_status，复用调用方事务游标"""
    if notify_time is not None:
        cur.execute("UPDATE reservation SET status = ?, notify_time = ? WHERE id = ?",
                    (status, notify_time, reservation_id))
    else:
        cur.execute("UPDATE reservation SET status = ? WHERE id = ?",
                    (status, reservation_id))
    return cur.rowcount
