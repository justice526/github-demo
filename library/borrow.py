import sqlite3
import os
from datetime import datetime, timedelta

def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    return sqlite3.connect(db_path)

def borrow_book(user_id, book_id):
    """借阅图书
    :param user_id: 用户编号
    :param book_id: 图书编号
    :return: True成功；False失败（图书已借出）
    """
    conn = get_conn()
    cur = conn.cursor()
    # 判断图书是否已经借出
    cur.execute("SELECT is_borrow FROM book WHERE id=?", (book_id,))
    res = cur.fetchone()
    if not res or res[0] == 1:
        conn.close()
        return False

    now = datetime.now()
    borrow_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    # 借阅期限7天，算出归还截止时间
    deadline = now + timedelta(days=7)
    deadline_str = deadline.strftime("%Y-%m-%d %H:%M:%S")

    # 修改图书状态为已借出
    cur.execute("UPDATE book SET is_borrow=1 WHERE id=?", (book_id,))
    # 新增借阅记录，存入 borrow_time、return_deadline，return_time、penalty初始为NULL/0
    cur.execute('''
        INSERT INTO borrow_record(user_id, book_id, borrow_time, return_deadline, return_time, penalty)
        VALUES (?, ?, ?, ?, NULL, 0)
    ''', (user_id, book_id, borrow_time_str, deadline_str))

    conn.commit()
    conn.close()
    return True


def return_book(book_id):
    """归还图书；超时自动计算罚款，每天0.5元"""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # 1.取出这条未归还记录的 归还截止日期
    cur.execute('''
        SELECT return_deadline FROM borrow_record
        WHERE book_id=? AND return_time IS NULL
    ''', (book_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False

    deadline_str = row[0]
    # 字符串转回datetime对象做时间对比
    deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")

    penalty = 0.0
    # 判断是否超时：当前时间 > 截止时间
    if now > deadline:
        # 计算相差多少天
        delta_day = (now - deadline).total_seconds() / (24 * 3600)
        penalty = round(delta_day * 0.5, 2)

    # 更新图书状态为未借出
    cur.execute("UPDATE book SET is_borrow=0 WHERE id=?", (book_id,))

    # 更新借阅记录：回填归还时间 + 写入计算出来的罚款penalty
    cur.execute('''
        UPDATE borrow_record
        SET return_time=?, penalty=?
        WHERE book_id=? AND return_time IS NULL
    ''', (now_str, penalty, book_id))

    conn.commit()
    conn.close()
    return penalty


def get_borrow_record(user_id):
    """查询某用户全部借阅记录，额外返回罚款penalty字段"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT br.id,b.title,br.borrow_time,br.return_deadline,br.return_time,br.penalty
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ?
    ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    # 自测：假设用户id=1，图书id=1
    ok = borrow_book(1,1)
    print("借阅结果", ok)
    records = get_borrow_record(1)
    print("借阅记录：", records)
