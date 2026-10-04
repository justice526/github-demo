"""标签数据访问层

表归属：本模块独占 `tag` 与 `book_tag` 两张表。

`book_tag` 用复合主键 (book_id, tag_id) 保证同一本书同一标签
只会关联一次，重复打标签靠 INSERT OR IGNORE 幂等处理。
"""

from core import db


def _to_tuple(row):
    return tuple(row) if row is not None else None


def _to_tuples(rows):
    return [tuple(r) for r in rows]


def init_table():
    """幂等建表"""
    with db.transaction() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS tag (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS book_tag (
            book_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (book_id, tag_id)
        )""")


def tables_ready():
    """两张表是否都已建（未建时上层应优雅降级）"""
    row = db.query_one("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE type = 'table' AND name IN ('tag', 'book_tag')
    """)
    return bool(row and row[0] == 2)


# ==================== 读 ====================

def find_all_tags():
    """全部标签：[(id, name), ...]，按名称排序"""
    if not tables_ready():
        return []
    return _to_tuples(db.query_all("SELECT id, name FROM tag ORDER BY name"))


def get_tag_id(cur, name):
    """在给定游标中查标签 ID（供建标签流程复用事务）"""
    cur.execute("SELECT id FROM tag WHERE name = ?", (name,))
    row = cur.fetchone()
    return row[0] if row else None


def tags_of_book(book_id):
    """某本书的标签名列表"""
    if not tables_ready():
        return []
    return [r[0] for r in db.query_all("""
        SELECT t.name FROM book_tag bt
        JOIN tag t ON bt.tag_id = t.id
        WHERE bt.book_id = ?
        ORDER BY t.name
    """, (book_id,))]


def tags_map():
    """book_id → [标签名, ...] 的映射，供列表批量展示"""
    if not tables_ready():
        return {}
    out = {}
    for bid, name in db.query_all("""
        SELECT bt.book_id, t.name FROM book_tag bt
        JOIN tag t ON bt.tag_id = t.id
        ORDER BY t.name
    """):
        out.setdefault(bid, []).append(name)
    return out


def books_by_tags(tag_names, match_all=False):
    """按标签筛选图书

    :param tag_names: 标签名列表
    :param match_all: True 要求全部命中，False 任一命中即可
    :return: [(id, title, author, category, is_borrow), ...]
    """
    if not tag_names or not tables_ready():
        return []
    names = list(dict.fromkeys(tag_names))  # 去重且保序
    placeholders = ",".join("?" * len(names))

    if match_all:
        sql = f"""
            SELECT b.id, b.title, b.author, b.category, b.is_borrow
            FROM book b
            WHERE b.id IN (
                SELECT bt.book_id FROM book_tag bt
                JOIN tag t ON bt.tag_id = t.id
                WHERE t.name IN ({placeholders})
                GROUP BY bt.book_id
                HAVING COUNT(DISTINCT t.name) = ?
            )
            ORDER BY b.id
        """
        params = tuple(names) + (len(names),)
    else:
        sql = f"""
            SELECT DISTINCT b.id, b.title, b.author, b.category, b.is_borrow
            FROM book b
            JOIN book_tag bt ON b.id = bt.book_id
            JOIN tag t ON bt.tag_id = t.id
            WHERE t.name IN ({placeholders})
            ORDER BY b.id
        """
        params = tuple(names)
    return _to_tuples(db.query_all(sql, params))


def stat():
    """标签统计

    :return: {total, used, links, tagged_books}
        total        标签总数
        used         实际被用到的标签数
        links        关联关系总数
        tagged_books 被打标签的图书数
    """
    if not tables_ready():
        return {"total": 0, "used": 0, "links": 0, "tagged_books": 0}
    total = db.query_one("SELECT COUNT(*) FROM tag")[0] or 0
    used = db.query_one("SELECT COUNT(DISTINCT tag_id) FROM book_tag")[0] or 0
    links = db.query_one("SELECT COUNT(*) FROM book_tag")[0] or 0
    tagged_books = db.query_one("SELECT COUNT(DISTINCT book_id) FROM book_tag")[0] or 0
    return {"total": total, "used": used, "links": links, "tagged_books": tagged_books}


def count_orphans():
    """没有任何图书使用的孤儿标签数"""
    if not tables_ready():
        return 0
    return db.query_one("""
        SELECT COUNT(*) FROM tag t
        WHERE NOT EXISTS (SELECT 1 FROM book_tag bt WHERE bt.tag_id = t.id)
    """)[0] or 0


# ==================== 写 ====================

def get_or_create_tag(cur, name):
    """取标签 ID，不存在则创建（复用调用方事务）"""
    tid = get_tag_id(cur, name)
    if tid is not None:
        return tid
    cur.execute("INSERT INTO tag(name) VALUES (?)", (name,))
    return cur.lastrowid


def link(book_id, tag_id):
    """关联图书与标签（幂等）"""
    with db.transaction() as cur:
        cur.execute("INSERT OR IGNORE INTO book_tag(book_id, tag_id) VALUES (?, ?)",
                    (book_id, tag_id))
        return cur.rowcount


def unlink(book_id, tag_id):
    """解除关联"""
    with db.transaction() as cur:
        cur.execute("DELETE FROM book_tag WHERE book_id = ? AND tag_id = ?",
                    (book_id, tag_id))
        return cur.rowcount


def unlink_by_name(book_id, tag_name):
    """按标签名解除关联；标签不存在时静默返回 0"""
    with db.transaction() as cur:
        cur.execute("""
            DELETE FROM book_tag WHERE book_id = ? AND tag_id = (
                SELECT id FROM tag WHERE name = ?
            )
        """, (book_id, tag_name))
        return cur.rowcount


def replace_all(book_id, tag_names):
    """覆盖式设置某本书的全部标签

    :return: 设置成功的标签数
    """
    names = [n for n in dict.fromkeys(tag_names) if n]
    with db.transaction() as cur:
        cur.execute("DELETE FROM book_tag WHERE book_id = ?", (book_id,))
        for name in names:
            tid = get_or_create_tag(cur, name)
            cur.execute("INSERT OR IGNORE INTO book_tag(book_id, tag_id) VALUES (?, ?)",
                        (book_id, tid))
    return len(names)


def add_some(book_id, tag_names):
    """追加标签（保留原有）"""
    names = [n for n in dict.fromkeys(tag_names) if n]
    with db.transaction() as cur:
        for name in names:
            tid = get_or_create_tag(cur, name)
            cur.execute("INSERT OR IGNORE INTO book_tag(book_id, tag_id) VALUES (?, ?)",
                        (book_id, tid))
    return len(names)


def delete_tag(name):
    """删除标签及其所有关联"""
    with db.transaction() as cur:
        cur.execute("DELETE FROM book_tag WHERE tag_id = (SELECT id FROM tag WHERE name = ?)",
                    (name,))
        cur.execute("DELETE FROM tag WHERE name = ?", (name,))
        return cur.rowcount


def purge_orphans():
    """清理没有任何图书使用的孤儿标签，返回清理条数"""
    with db.transaction() as cur:
        cur.execute("""
            DELETE FROM tag WHERE NOT EXISTS (
                SELECT 1 FROM book_tag WHERE book_tag.tag_id = tag.id
            )
        """)
        return cur.rowcount
