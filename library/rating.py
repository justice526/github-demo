"""图书评分与评论模块

独立维护 rating 表，首次使用会自动建表（幂等），
不影响 db.py 的原有建表逻辑。
"""
import sqlite3
import os
from datetime import datetime


def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_rating_table():
    """创建 rating 表（不存在时才创建）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            score REAL NOT NULL,
            comment TEXT DEFAULT '',
            create_time TEXT,
            UNIQUE(user_id, book_id)
        )
    ''')
    conn.commit()
    conn.close()
    return True


def rate_book(user_id, book_id, score, comment=""):
    """给图书评分（1~5 分）
    同一用户对同一本书重复评分时覆盖更新。
    :return: True 成功 / False 失败
    """
    try:
        score = float(score)
    except (TypeError, ValueError):
        return False
    if score < 1 or score > 5:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute('''
            INSERT INTO rating(user_id, book_id, score, comment, create_time)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, book_id) DO UPDATE SET
                score = excluded.score,
                comment = excluded.comment,
                create_time = excluded.create_time
        ''', (user_id, book_id, score, comment or "", now))
        conn.commit()
        return True
    except Exception as e:
        print("评分失败：", e)
        return False
    finally:
        conn.close()


def get_book_rating(book_id, user_id=None):
    """获取某本书的评分概况
    :return: {"avg": 平均分, "count": 评分人数, "my_score": 我的评分或 None, "my_comment": 我的评论}
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT AVG(score), COUNT(*) FROM rating WHERE book_id = ?", (book_id,))
    row = cur.fetchone()
    avg = round(row[0], 1) if row and row[0] is not None else 0.0
    cnt = (row[1] if row else 0) or 0

    my_score, my_comment = None, ""
    if user_id is not None:
        cur.execute("SELECT score, comment FROM rating WHERE book_id = ? AND user_id = ?",
                    (book_id, user_id))
        r = cur.fetchone()
        if r:
            my_score, my_comment = r[0], r[1] or ""
    conn.close()
    return {"avg": avg, "count": cnt, "my_score": my_score, "my_comment": my_comment}


def get_ratings_map():
    """批量获取全部图书评分：{book_id: {"avg": x, "count": n}}"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT book_id, AVG(score), COUNT(*) FROM rating GROUP BY book_id")
    data = {}
    for row in cur.fetchall():
        data[row[0]] = {"avg": round(row[1], 1), "count": row[2]}
    conn.close()
    return data


def get_top_rated(top_n=5, min_count=1):
    """好评排行榜：按平均分降序
    :param min_count: 至少需要几人评分才上榜
    :return: [(book_id, title, author, avg, count), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT b.id, b.title, b.author, ROUND(AVG(r.score), 1), COUNT(r.id)
        FROM rating r
        LEFT JOIN book b ON r.book_id = b.id
        GROUP BY r.book_id
        HAVING COUNT(r.id) >= ?
        ORDER BY AVG(r.score) DESC, COUNT(r.id) DESC
        LIMIT ?
    ''', (min_count, top_n))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_book_comments(book_id, limit=20):
    """获取某本书的文字评论（含用户名）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT u.username, r.score, r.comment, r.create_time
        FROM rating r
        LEFT JOIN user u ON r.user_id = u.id
        WHERE r.book_id = ? AND r.comment IS NOT NULL AND r.comment != ''
        ORDER BY r.create_time DESC
        LIMIT ?
    ''', (book_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_rating(user_id, book_id):
    """撤销自己对某本书的评分"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM rating WHERE user_id = ? AND book_id = ?", (user_id, book_id))
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n > 0


def star_text(avg):
    """把平均分转成星号文本，例如 4.5 -> ★★★★☆"""
    try:
        avg = float(avg)
    except (TypeError, ValueError):
        return "☆☆☆☆☆"
    full = int(avg + 0.5)
    full = max(0, min(5, full))
    return "★" * full + "☆" * (5 - full)


if __name__ == "__main__":
    init_rating_table()
    print("rating 模块加载完成，rating 表已就绪")
