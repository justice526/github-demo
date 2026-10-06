"""借阅数据访问层

只写 SQL。借阅规则（上限、逾期禁借、欠费暂停）、罚款计算、
预约优先权等判断属于 service 层。

表归属：本模块独占 `borrow_record` 表。

**事务要点**：借阅要同时改 `book.is_borrow` 与插 `borrow_record`，
归还要同时改两处并结清罚款。这些跨表写入必须用
`core.db.transaction()` 包起来，避免出现「状态改了但记录没写」
这种不一致。旧实现是分多次 commit 的，属于隐患。
"""

from datetime import datetime

from core import db


def _to_tuple(row):
    return tuple(row) if row is not None else None


def _to_tuples(rows):
    return [tuple(r) for r in rows]


# ==================== 读 ====================

def find_active_by_user_book(user_id, book_id):
    """查某用户对某书的未归还记录，不存在返回 None

    返回 sqlite3.Row（可用 `record["id"]` 按列名访问，也可 `record[0]`
    按下标访问）。这里刻意不做 tuple 转换：归还与续借要按列名取值，
    按位置解包在查询列增减时会静默错位。
    """
    return db.query_one("""
        SELECT id, user_id, book_id, borrow_time, return_deadline, return_time, penalty
        FROM borrow_record
        WHERE user_id = ? AND book_id = ? AND return_time IS NULL
    """, (user_id, book_id))


def find_by_user(user_id):
    """某用户全部借阅记录（含已归还）"""
    return _to_tuples(db.query_all("""
        SELECT br.id, b.title, br.borrow_time, br.return_deadline,
               br.return_time, br.penalty
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ?
        ORDER BY br.id DESC
    """, (user_id,)))


def find_active_by_user(user_id):
    """某用户**未归还**的记录（含 book_id，供 Web 层归还操作定位图书）

    返回 (record_id, book_id, title, borrow_time, deadline) 元组列表。
    """
    return _to_tuples(db.query_all("""
        SELECT br.id, br.book_id, b.title, br.borrow_time, br.return_deadline
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ? AND br.return_time IS NULL
        ORDER BY br.borrow_time DESC
    """, (user_id,)))


def find_all():
    """全部借阅记录（导出用）"""
    return _to_tuples(db.query_all("""
        SELECT br.id, u.username, b.title, br.borrow_time,
               br.return_deadline, br.return_time, br.penalty
        FROM borrow_record br
        LEFT JOIN user u ON br.user_id = u.id
        LEFT JOIN book b ON br.book_id = b.id
        ORDER BY br.id
    """))


def find_history_by_book(book_id, limit=30):
    """某本书的借阅历史：[(id, user_id, borrow_time, deadline, return_time), ...]"""
    return _to_tuples(db.query_all("""
        SELECT id, user_id, borrow_time, return_deadline, return_time
        FROM borrow_record
        WHERE book_id = ?
        ORDER BY borrow_time DESC
        LIMIT ?
    """, (book_id, limit)))


def count_unreturned_by_user(user_id):
    """某用户未归还的图书数"""
    return db.query_one(
        "SELECT COUNT(*) FROM borrow_record WHERE user_id = ? AND return_time IS NULL",
        (user_id,))[0]


def sum_unpaid_penalty(user_id):
    """某用户未缴罚款总额"""
    row = db.query_one(
        "SELECT COALESCE(SUM(penalty), 0) FROM borrow_record "
        "WHERE user_id = ? AND penalty > 0", (user_id,))
    return row[0] or 0.0


def count_unreturned_by_book(book_id):
    """某书未归还的借阅数（删除图书前的安全校验用）"""
    return db.query_one(
        "SELECT COUNT(*) FROM borrow_record WHERE book_id = ? AND return_time IS NULL",
        (book_id,))[0]


def find_overdue_raw(user_id):
    """未归还记录的原始行（逾期天数与罚款由 service 计算）

    返回 (record_id, title, borrow_time, deadline) 元组列表。
    """
    return _to_tuples(db.query_all("""
        SELECT br.id, b.title, br.borrow_time, br.return_deadline
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ? AND br.return_time IS NULL
    """, (user_id,)))


def find_due_soon_raw(user_id):
    """未归还且未逾期的记录（到期提醒用），含借阅天数参数由 service 算"""
    return _to_tuples(db.query_all("""
        SELECT br.id, b.title, br.borrow_time, br.return_deadline
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ? AND br.return_time IS NULL
    """, (user_id,)))


# ==================== 写 ====================

def insert(user_id, book_id, borrow_time, deadline, penalty=0.0):
    """新增借阅记录，返回记录 ID"""
    with db.transaction() as cur:
        cur.execute("""
            INSERT INTO borrow_record(user_id, book_id, borrow_time,
                                      return_deadline, return_time, penalty)
            VALUES (?, ?, ?, ?, NULL, ?)
        """, (user_id, book_id, borrow_time, deadline, penalty))
        return cur.lastrowid


def mark_returned(record_id, return_time, penalty=0.0):
    """标记归还并写入最终罚款"""
    with db.transaction() as cur:
        cur.execute("""
            UPDATE borrow_record
            SET return_time = ?, penalty = ?
            WHERE id = ?
        """, (return_time, penalty, record_id))
        return cur.rowcount


def insert_in(cur, user_id, book_id, borrow_time, deadline, penalty=0.0):
    """同 insert，复用调用方事务游标（借阅时与改 book 状态必须原子）"""
    cur.execute("""
        INSERT INTO borrow_record(user_id, book_id, borrow_time,
                                  return_deadline, return_time, penalty)
        VALUES (?, ?, ?, ?, NULL, ?)
    """, (user_id, book_id, borrow_time, deadline, penalty))
    return cur.lastrowid


def mark_returned_in(cur, record_id, return_time, penalty=0.0):
    """同 mark_returned，复用调用方事务游标"""
    cur.execute("""
        UPDATE borrow_record
        SET return_time = ?, penalty = ?
        WHERE id = ?
    """, (return_time, penalty, record_id))
    return cur.rowcount


def extend_deadline(record_id, new_deadline):
    """续借：延长应还时间"""
    with db.transaction() as cur:
        cur.execute("UPDATE borrow_record SET return_deadline = ? WHERE id = ?",
                    (new_deadline, record_id))
        return cur.rowcount


def clear_penalty_by_user(user_id):
    """结清某用户全部未缴罚款，返回受影响行数

    缴罚款时与扣余额必须在同一事务内，本函数接受外部传入的游标。
    """
    return db.execute(
        "UPDATE borrow_record SET penalty = 0 WHERE user_id = ? AND penalty > 0",
        (user_id,))


def clear_penalty_by_user_in(cur, user_id):
    """同 clear_penalty_by_user，但复用调用方的事务游标

    缴款场景必须用这个版本：扣钱与结清要原子生效。
    """
    cur.execute("UPDATE borrow_record SET penalty = 0 WHERE user_id = ? AND penalty > 0",
                (user_id,))
    return cur.rowcount


def get_penalty(record_id):
    """取某条记录的罚款金额"""
    row = db.query_one("SELECT penalty FROM borrow_record WHERE id = ?", (record_id,))
    return row[0] if row else 0.0


def get_deadline(record_id):
    row = db.query_one("SELECT return_deadline FROM borrow_record WHERE id = ?", (record_id,))
    return row[0] if row else None


def get_borrow_time(record_id):
    row = db.query_one("SELECT borrow_time FROM borrow_record WHERE id = ?", (record_id,))
    return row[0] if row else None
