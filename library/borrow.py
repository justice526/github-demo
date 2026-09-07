import sqlite3
import os
from datetime import datetime

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

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 修改图书状态为已借出
    cur.execute("UPDATE book SET is_borrow=1 WHERE id=?", (book_id,))
    # 新增一条借阅记录，归还时间留空
    cur.execute('''
        INSERT INTO borrow_record(user_id, book_id, borrow_time, return_time)
        VALUES (?, ?, ?, NULL)
    ''', (user_id, book_id, now))
    conn.commit()
    conn.close()
    return True


def return_book(book_id):
    """归还图书"""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 更新图书状态为未借出
    cur.execute("UPDATE book SET is_borrow=0 WHERE id=?", (book_id,))
    # 填写归还时间
    cur.execute('''
        UPDATE borrow_record
        SET return_time=?
        WHERE book_id=? AND return_time IS NULL
    ''', (now, book_id))
    conn.commit()
    conn.close()


def get_borrow_record(user_id):
    """查询某用户全部借阅记录"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT br.id,b.title,br.borrow_time,br.return_time
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
