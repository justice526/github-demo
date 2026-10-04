"""图书数据访问层

只写 SQL，不含任何业务规则。业务判断（如"有未归还借阅则不能删"）
属于 service 层；这里只负责取数与写数。

**返回格式约定（重要）**：为保持向后兼容，查询一律返回
`sqlite3.Row` 转成的**元组**，字段顺序与旧 SQL 完全一致：
    (id, title, author, category, is_borrow)
GUI 与 CLI 大量使用 `row[0]` 这类下标访问，改动会导致界面崩溃。
"""

from core import db

# 统一的图书查询列，保证所有查询返回结构一致
_BOOK_COLUMNS = "id, title, author, category, is_borrow"


def _to_tuple(row):
    """sqlite3.Row → 普通元组（保持旧的下标访问方式）"""
    return tuple(row) if row is not None else None


def _to_tuples(rows):
    return [tuple(r) for r in rows]


# ==================== 读 ====================

def find_all():
    """全部图书"""
    return _to_tuples(db.query_all(f"SELECT {_BOOK_COLUMNS} FROM book"))


def find_by_id(book_id):
    """按 ID 查单本，不存在返回 None"""
    return _to_tuple(db.query_one(
        f"SELECT {_BOOK_COLUMNS} FROM book WHERE id = ?", (book_id,)))


def find_by_title_or_author(keyword):
    """书名或作者模糊匹配"""
    kw = f"%{keyword}%"
    return _to_tuples(db.query_all(
        f"SELECT {_BOOK_COLUMNS} FROM book WHERE title LIKE ? OR author LIKE ?",
        (kw, kw)))


def find_by_category(category):
    """按分类精确查询"""
    return _to_tuples(db.query_all(
        f"SELECT {_BOOK_COLUMNS} FROM book WHERE category = ?", (category,)))


def exists(book_id):
    """图书是否存在"""
    row = db.query_one("SELECT 1 FROM book WHERE id = ?", (book_id,))
    return row is not None


def get_title(book_id):
    """只取书名（供 log / rating 等模块拼接日志用，避免它们直接查 book 表）"""
    row = db.query_one("SELECT title FROM book WHERE id = ?", (book_id,))
    return row[0] if row else None


def count_all():
    return db.query_one("SELECT COUNT(*) FROM book")[0]


def count_by_category():
    """各分类统计：[(category, total, in_stock, borrowed), ...]

    注意：category 保持数据库原样（可能是 None），由 service 决定如何展示，
    这里不做 COALESCE 替换，以免改变既有行为。
    """
    return _to_tuples(db.query_all("""
        SELECT category,
               COUNT(*) AS total,
               SUM(CASE WHEN is_borrow = 0 THEN 1 ELSE 0 END) AS in_stock,
               SUM(CASE WHEN is_borrow = 1 THEN 1 ELSE 0 END) AS borrowed
        FROM book
        GROUP BY category
    """))


def hot_rank(top_n):
    """热门借阅排行榜：[(id, title, author, borrow_count), ...]"""
    return _to_tuples(db.query_all("""
        SELECT b.id, b.title, b.author, COUNT(br.id) AS borrow_count
        FROM book b
        LEFT JOIN borrow_record br ON b.id = br.book_id
        GROUP BY b.id, b.title, b.author
        ORDER BY borrow_count DESC
        LIMIT ?
    """, (top_n,)))


def count_borrowed_by_book():
    """每本书的累计借阅次数：[(book_id, times), ...]，用于排行榜"""
    return _to_tuples(db.query_all("""
        SELECT b.id, COUNT(br.id) AS times
        FROM book b
        LEFT JOIN borrow_record br ON br.book_id = b.id
        GROUP BY b.id
        HAVING times > 0
        ORDER BY times DESC, b.id
    """))


def all_categories():
    """全部分类名（去重、已排序）"""
    return [r[0] for r in db.query_all(
        "SELECT DISTINCT category FROM book WHERE category IS NOT NULL "
        "AND category != '' ORDER BY category")]


def status_of(book_id):
    """借阅状态：0=在架 1=已借出；图书不存在返回 None"""
    row = db.query_one("SELECT is_borrow FROM book WHERE id = ?", (book_id,))
    return row[0] if row else None


# ==================== 写 ====================

def insert(title, author, category):
    """新增图书，返回新书 ID"""
    with db.transaction() as cur:
        cur.execute(
            "INSERT INTO book(title, author, category, is_borrow) VALUES (?, ?, ?, 0)",
            (title, author, category))
        return cur.lastrowid


def update(book_id, new_title, new_author, new_category=None):
    """修改图书信息；new_category 为 None 时保持原分类

    :return: 受影响行数（0 表示图书不存在）
    """
    with db.transaction() as cur:
        if new_category is None:
            cur.execute("UPDATE book SET title=?, author=? WHERE id=?",
                        (new_title, new_author, book_id))
        else:
            cur.execute("UPDATE book SET title=?, author=?, category=? WHERE id=?",
                        (new_title, new_author, new_category, book_id))
        return cur.rowcount


def delete(book_id):
    """删除图书，返回受影响行数"""
    with db.transaction() as cur:
        cur.execute("DELETE FROM book WHERE id = ?", (book_id,))
        return cur.rowcount


def set_borrow_status(book_id, is_borrow):
    """更新借阅状态（借出/归还时由 service 调用）"""
    with db.transaction() as cur:
        cur.execute("UPDATE book SET is_borrow=? WHERE id=?", (1 if is_borrow else 0, book_id))
        return cur.rowcount


def set_borrow_status_in(cur, book_id, is_borrow):
    """同 set_borrow_status，复用调用方事务游标

    借阅/归还要同时改 book 与 borrow_record，必须原子生效，
    故由 borrow_service 在同一事务里调用。
    """
    cur.execute("UPDATE book SET is_borrow = ? WHERE id = ?",
                (1 if is_borrow else 0, book_id))
    return cur.rowcount


def delete_all():
    """清空全部图书（恢复备份时用）"""
    with db.transaction() as cur:
        cur.execute("DELETE FROM book")
        return cur.rowcount


def bulk_insert(books):
    """批量插入，返回插入条数

    :param books: [(title, author, category), ...]
    """
    with db.transaction() as cur:
        cur.executemany(
            "INSERT INTO book(title, author, category, is_borrow) VALUES (?, ?, ?, 0)",
            books)
        return cur.rowcount


# ==================== 备份 / 恢复 ====================

def dump_all():
    """导出全部图书为可 JSON 序列化的字典列表"""
    return [
        {"id": r[0], "title": r[1], "author": r[2],
         "category": r[3], "is_borrow": r[4]}
        for r in find_all()
    ]


def restore(rows, overwrite=False):
    """从备份数据恢复

    :param rows: [{"title","author","category","is_borrow"}, ...]
    :param overwrite: True 先清空 book 表
    :return: 导入条数
    """
    with db.transaction() as cur:
        if overwrite:
            cur.execute("DELETE FROM book")
        for b in rows:
            cur.execute(
                "INSERT INTO book(title, author, category, is_borrow) VALUES (?, ?, ?, ?)",
                (b.get("title"), b.get("author"), b.get("category"), b.get("is_borrow", 0)))
        return len(rows)


# ==================== 分页 / 排序 / 组合查询 ====================

# 排序字段白名单，防 SQL 注入
SORT_FIELDS = ("id", "title", "author", "category")


def find_page(page, page_size=5):
    """分页查询，返回 (当页图书列表, 总条数)"""
    offset = (page - 1) * page_size
    books = _to_tuples(db.query_all(
        f"SELECT {_BOOK_COLUMNS} FROM book LIMIT ? OFFSET ?", (page_size, offset)))
    total = count_all()
    return books, total


def find_sorted(sort_by="id", order="asc"):
    """按指定字段排序，字段与方向均走白名单"""
    if sort_by not in SORT_FIELDS:
        sort_by = "id"
    order = "desc" if str(order).lower() == "desc" else "asc"
    return _to_tuples(db.query_all(
        f"SELECT {_BOOK_COLUMNS} FROM book ORDER BY {sort_by} {order}"))


def advanced_search(title_kw=None, author_kw=None, category=None, status=None,
                    sort_by="id", order="asc"):
    """多条件组合搜索

    :param status: 0=在架 1=已借出，None 或空串表示不限
    :return: [(id, title, author, category, is_borrow), ...]
    """
    if sort_by not in SORT_FIELDS:
        sort_by = "id"
    order = "desc" if str(order).lower() == "desc" else "asc"

    sql = f"SELECT {_BOOK_COLUMNS} FROM book WHERE 1=1"
    params = []
    if title_kw:
        sql += " AND title LIKE ?"
        params.append(f"%{title_kw}%")
    if author_kw:
        sql += " AND author LIKE ?"
        params.append(f"%{author_kw}%")
    if category:
        sql += " AND category = ?"
        params.append(category)
    if status is not None and str(status) != "":
        # 先把 status 转成 int，转不动就整条忽略这个条件。
        # 不能先往 SQL 里拼占位符再 append 参数 —— 转换失败时
        # 参数没加上而 SQL 里的 '?' 还在，执行会直接报
        # "Incorrect number of bindings supplied"。旧实现就有这个缺陷。
        try:
            status_val = int(status)
        except (TypeError, ValueError):
            status_val = None
        if status_val is not None:
            sql += " AND is_borrow = ?"
            params.append(status_val)
    sql += f" ORDER BY {sort_by} {order}"
    return _to_tuples(db.query_all(sql, tuple(params)))


def borrow_count_of(book_id):
    """某本书的历史借阅总次数"""
    return db.query_one(
        "SELECT COUNT(*) FROM borrow_record WHERE book_id = ?", (book_id,))[0]


def current_borrower_name(book_id):
    """当前借阅人用户名；未借出返回 None"""
    row = db.query_one("""
        SELECT u.username FROM borrow_record br
        LEFT JOIN user u ON br.user_id = u.id
        WHERE br.book_id = ? AND br.return_time IS NULL
        ORDER BY br.borrow_time DESC LIMIT 1
    """, (book_id,))
    return row[0] if row else None


def dashboard():
    """仪表盘统计：{total_book, borrowed, available, category_info}"""
    total = count_all()
    borrowed = db.query_one("SELECT COUNT(*) FROM book WHERE is_borrow = 1")[0]
    cat_info = _to_tuples(db.query_all(
        "SELECT category, COUNT(*) FROM book GROUP BY category"))
    return {
        "total_book": total,
        "borrowed": borrowed,
        "available": total - borrowed,
        "category_info": cat_info,
    }


def raw_unreturned_by_user(user_id):
    """某用户所有未归还记录的原始行

    返回 (record_id, title, borrow_time, return_deadline) 元组列表。
    逾期天数与罚款金额由 service 层计算（属于业务规则）。
    """
    return _to_tuples(db.query_all("""
        SELECT br.id, b.title, br.borrow_time, br.return_deadline
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ? AND br.return_time IS NULL
    """, (user_id,)))
