"""评分数据访问层

表归属：本模块独占 `rating` 表。
建表逻辑（init_rating_table）保留在本 repo 的 `init_table()`，
由 main.py / 适配层在启动时调用一次。
"""

from datetime import datetime

from core import db


def _to_tuple(row):
    return tuple(row) if row is not None else None


def _to_tuples(rows):
    return [tuple(r) for r in rows]


def init_table():
    """幂等建表（保留旧表结构，不加 IF NOT EXISTS 以外的行为变更）"""
    with db.transaction() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rating (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                comment TEXT DEFAULT '',
                create_time TEXT,
                UNIQUE(user_id, book_id)
            )
        """)


def table_ready():
    """表是否已建（未建时上层应优雅降级而不是抛异常）"""
    return db.table_exists("rating")


# ==================== 写 ====================

def upsert(user_id, book_id, score, comment=""):
    """写入或覆盖评分（一人一书只保留一条）

    :return: 受影响行数
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db.transaction() as cur:
        cur.execute("""
            INSERT INTO rating(user_id, book_id, score, comment, create_time)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, book_id) DO UPDATE SET
                score = excluded.score,
                comment = excluded.comment,
                create_time = excluded.create_time
        """, (user_id, book_id, score, comment or "", now))
        return cur.rowcount


def delete(user_id, book_id):
    """撤销评分"""
    with db.transaction() as cur:
        cur.execute("DELETE FROM rating WHERE user_id = ? AND book_id = ?",
                    (user_id, book_id))
        return cur.rowcount


# ==================== 读 ====================

def find_by_book(book_id):
    """某书的全部评分：[(user_id, score, comment, create_time), ...]"""
    return _to_tuples(db.query_all("""
        SELECT user_id, score, comment, create_time
        FROM rating WHERE book_id = ?
        ORDER BY create_time DESC
    """, (book_id,)))


def find_one(user_id, book_id):
    """某用户对某书的评分，不存在返回 None

    返回 sqlite3.Row，调用方按列名取值（score / comment）。
    """
    return db.query_one("""
        SELECT user_id, score, comment, create_time
        FROM rating WHERE user_id = ? AND book_id = ?
    """, (user_id, book_id))


def stats_of(book_id):
    """某书的评分统计：(平均分, 评分人数)，无人评分时 (0, 0)"""
    row = db.query_one("""
        SELECT COALESCE(AVG(score), 0), COUNT(*)
        FROM rating WHERE book_id = ?
    """, (book_id,))
    return (row[0] or 0, row[1] or 0) if row else (0, 0)


def all_stats():
    """全部图书的评分统计：[(book_id, 平均分, 人数), ...]"""
    return _to_tuples(db.query_all("""
        SELECT book_id, COALESCE(AVG(score), 0) AS avg_score, COUNT(*) AS cnt
        FROM rating GROUP BY book_id
    """))


def comments_of(book_id, limit=20):
    """某书的读者评论（含用户名），最新在前"""
    return _to_tuples(db.query_all("""
        SELECT r.user_id, u.username, r.score, r.comment, r.create_time
        FROM rating r
        LEFT JOIN user u ON r.user_id = u.id
        WHERE r.book_id = ? AND r.comment IS NOT NULL AND r.comment != ''
        ORDER BY r.create_time DESC
        LIMIT ?
    """, (book_id, limit)))


def top_rated(top_n=5, min_count=1):
    """高分榜：(book_id, 平均分, 人数)，按均分降序"""
    return _to_tuples(db.query_all("""
        SELECT book_id, AVG(score) AS avg_score, COUNT(*) AS cnt
        FROM rating
        GROUP BY book_id
        HAVING COUNT(*) >= ?
        ORDER BY avg_score DESC, cnt DESC, book_id
        LIMIT ?
    """, (min_count, top_n)))


def count_all():
    row = db.query_one("SELECT COUNT(*) FROM rating")
    return row[0] if row else 0
