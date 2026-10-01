"""图书预约排队模块

业务规则：
- 图书在架时不能预约（直接借阅即可），仅「已借出」的图书可预约排队
- 同一用户对同一本书只能有一条活跃预约（waiting 或 ready）
- 有逾期未还或欠费超阈值的用户不允许预约
- 图书归还后，队首 waiting 自动变为 ready（通知到书）
- ready 状态的预约人享有优先取书权，其他人不能抢借该书
- 预约人成功借到该书后，预约自动标记为 done

状态说明：waiting 排队中 / ready 已到书待取 / done 已借到 / cancelled 已取消
"""
import sqlite3
import os
from datetime import datetime

from rules import check_borrow_permission, get_borrow_summary


def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_reservation_table():
    """创建预约表（幂等）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reservation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            reserve_time TEXT,
            status TEXT DEFAULT 'waiting',
            notify_time TEXT
        )
    ''')
    conn.commit()
    conn.close()
    return True


# ========== 预约 / 取消 ==========
def reserve_book(user_id, book_id):
    """预约一本已被借出的图书
    :return: (ok: bool, msg: str)
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title, is_borrow FROM book WHERE id = ?", (book_id,))
        book = cur.fetchone()
        if not book:
            return False, "图书不存在"
        title = book[1]

        if book[2] == 0:
            return False, f"《{title}》当前在架可借，直接借阅即可，无需预约"

        # 是否已经借了这本书没还
        cur.execute('''
            SELECT COUNT(*) FROM borrow_record
            WHERE user_id = ? AND book_id = ? AND return_time IS NULL
        ''', (user_id, book_id))
        if cur.fetchone()[0] > 0:
            return False, f"你已借有《{title}》，无需预约"

        # 是否已有活跃预约
        cur.execute('''
            SELECT status FROM reservation
            WHERE user_id = ? AND book_id = ? AND status IN ('waiting', 'ready')
        ''', (user_id, book_id))
        row = cur.fetchone()
        if row:
            if row[0] == "ready":
                return False, f"你预约的《{title}》已到书，请前往借阅"
            return False, f"你已在《{title}》的预约队列中，无需重复预约"

        # 逾期 / 欠费用户不允许预约
        s = get_borrow_summary(user_id)
        if s["overdue"] > 0:
            return False, f"你有 {s['overdue']} 本图书逾期未还，请先归还"
        if s["unpaid_fine"] >= s["fine_threshold"] > 0:
            return False, f"你有 {s['unpaid_fine']} 元罚款未结清，请先缴纳"

        cur.execute('''
            INSERT INTO reservation(user_id, book_id, reserve_time, status, notify_time)
            VALUES (?, ?, ?, 'waiting', NULL)
        ''', (user_id, book_id, _now()))
        conn.commit()

        cur.execute('''
            SELECT COUNT(*) FROM reservation
            WHERE book_id = ? AND status = 'waiting'
        ''', (book_id,))
        ahead = cur.fetchone()[0]
        return True, f"预约成功！你在《{title}》队列中排第 {ahead} 位"
    except Exception as e:
        print("预约异常：", e)
        return False, f"预约失败：{e}"
    finally:
        conn.close()


def cancel_reservation(user_id, book_id):
    """取消自己的预约
    :return: (ok: bool, msg: str)
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT id, status FROM reservation
            WHERE user_id = ? AND book_id = ? AND status IN ('waiting', 'ready')
            ORDER BY id DESC LIMIT 1
        ''', (user_id, book_id))
        row = cur.fetchone()
        if not row:
            return False, "没有找到可取消的预约记录"
        was_ready = row[1] == "ready"
        cur.execute("UPDATE reservation SET status = 'cancelled' WHERE id = ?", (row[0],))
        conn.commit()

        # 若取消的是已到书的预约，把机会顺延给下一位
        if was_ready:
            cur.execute("SELECT title FROM book WHERE id = ?", (book_id,))
            b = cur.fetchone()
            _promote_next(cur, book_id)
            conn.commit()
            return True, f"已取消《{b[0] if b else ''}》的预约，名额已顺延给下一位"
        return True, "预约已取消"
    except Exception as e:
        print("取消预约异常：", e)
        return False, f"取消失败：{e}"
    finally:
        conn.close()


# ========== 查询 ==========
def get_my_reservations(user_id, include_history=False):
    """我的预约列表
    :return: [(记录ID, 图书ID, 书名, 预约时间, 状态, 通知时间, 排队位次), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    sql = '''
        SELECT r.id, r.book_id, b.title, r.reserve_time, r.status, r.notify_time
        FROM reservation r
        LEFT JOIN book b ON r.book_id = b.id
        WHERE r.user_id = ?
    '''
    if not include_history:
        sql += " AND r.status IN ('waiting', 'ready')"
    sql += " ORDER BY r.reserve_time DESC, r.id DESC"
    cur.execute(sql, (user_id,))
    rows = cur.fetchall()

    result = []
    for r in rows:
        pos = ""
        if r[4] == "ready":
            pos = "已到书"
        elif r[4] == "waiting":
            cur.execute('''
                SELECT COUNT(*) FROM reservation
                WHERE book_id = ? AND status = 'waiting' AND id < ?
            ''', (r[1], r[0]))
            pos = f"第 {cur.fetchone()[0] + 1} 位"
        result.append((r[0], r[1], r[2], r[3], _status_text(r[4]), r[5], pos))
    conn.close()
    return result


def _status_text(s):
    return {"waiting": "排队中", "ready": "已到书", "done": "已借到", "cancelled": "已取消"}.get(s, s)


def get_book_queue(book_id):
    """某本书的预约队列
    :return: [(用户名, 预约时间, 状态文本, 位次), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT u.username, r.reserve_time, r.status
        FROM reservation r
        LEFT JOIN user u ON r.user_id = u.id
        WHERE r.book_id = ? AND r.status IN ('waiting', 'ready')
        ORDER BY r.reserve_time ASC, r.id ASC
    ''', (book_id,))
    rows = cur.fetchall()
    conn.close()
    out = []
    for i, r in enumerate(rows):
        out.append((r[0] or "已注销用户", r[1], _status_text(r[2]), i + 1))
    return out


def get_reservation_count(book_id):
    """该书当前排队人数（含已到书未取）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT COUNT(*) FROM reservation
        WHERE book_id = ? AND status IN ('waiting', 'ready')
    ''', (book_id,))
    n = cur.fetchone()[0] or 0
    conn.close()
    return n


def get_my_queue_position(user_id, book_id):
    """我在该书队列中的位次；已到书返回 0；未预约返回 None"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, status FROM reservation
        WHERE user_id = ? AND book_id = ? AND status IN ('waiting', 'ready')
        ORDER BY id DESC LIMIT 1
    ''', (user_id, book_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    my_id, status = row
    if status == "ready":
        conn.close()
        return 0
    cur.execute('''
        SELECT COUNT(*) FROM reservation
        WHERE book_id = ? AND status = 'waiting' AND id < ?
    ''', (book_id, my_id))
    ahead = cur.fetchone()[0]
    conn.close()
    return ahead + 1


def get_ready_for_user(user_id):
    """我已预约到书、等待取书的图书
    :return: [(图书ID, 书名, 到书时间), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT r.book_id, b.title, r.notify_time
        FROM reservation r
        LEFT JOIN book b ON r.book_id = b.id
        WHERE r.user_id = ? AND r.status = 'ready'
        ORDER BY r.notify_time ASC
    ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def has_priority_holder(book_id, user_id):
    """该书是否有「别人」已预约到书。若有，则其他人不应抢借"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM reservation WHERE book_id = ? AND status = 'ready'", (book_id,))
    rows = cur.fetchall()
    conn.close()
    return any(r[0] != user_id for r in rows)


# ========== 队列推进（由归还 / 借阅动作触发） ==========
def _promote_next(cur, book_id):
    """内部函数：把队首 waiting 提升为 ready（要求当前无 ready 记录）"""
    cur.execute("SELECT COUNT(*) FROM reservation WHERE book_id = ? AND status = 'ready'", (book_id,))
    if cur.fetchone()[0] > 0:
        return None
    cur.execute('''
        SELECT r.id, r.user_id, u.username
        FROM reservation r
        LEFT JOIN user u ON r.user_id = u.id
        WHERE r.book_id = ? AND r.status = 'waiting'
        ORDER BY r.reserve_time ASC, r.id ASC LIMIT 1
    ''', (book_id,))
    row = cur.fetchone()
    if not row:
        return None
    cur.execute("UPDATE reservation SET status = 'ready', notify_time = ? WHERE id = ?",
                (_now(), row[0]))
    return {"user_id": row[1], "username": row[2]}


def on_book_returned(book_id):
    """图书归还后调用：推进预约队列，返回被通知的用户信息或 None"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        info = _promote_next(cur, book_id)
        conn.commit()
        return info
    except Exception as e:
        print("推进预约队列异常：", e)
        return None
    finally:
        conn.close()


def on_book_borrowed(user_id, book_id):
    """成功借阅后调用：把自己的活跃预约标记为已完成

    注意：此处**不**推进队列。因为书刚被借走，处于「已借出」状态，
    队列中的下一位应继续排队，直到该书真正归还时才由 on_book_returned 提升。
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE reservation SET status = 'done'
            WHERE user_id = ? AND book_id = ? AND status IN ('waiting', 'ready')
        ''', (user_id, book_id))
        conn.commit()
        return True
    except Exception as e:
        print("更新预约状态异常：", e)
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    init_reservation_table()
    print("reservation 模块加载完成")
