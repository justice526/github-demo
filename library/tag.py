"""图书标签模块

标签是图书的柔性分类（与 category 固定分类互补）：
- 分类如「计算机」「历史」是书目的固有属性，一个图书只有一个分类
- 标签如「入门」「面试必备」「经典」可自由组合，一本书可以有多个标签

表结构：
- tag(id, name UNIQUE)         标签字典
- book_tag(book_id, tag_id)    多对多关联，复合主键防重复
"""
import sqlite3
import os


def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_tag_table():
    """创建标签表（幂等）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tag (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS book_tag (
            book_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (book_id, tag_id)
        )
    ''')
    conn.commit()
    conn.close()
    return True


def _clean(names):
    """规整标签输入：去空白、去空项、去重、限长"""
    result, seen = [], set()
    for n in names or []:
        n = str(n).strip()
        if not n or n in seen:
            continue
        if len(n) > 12:      # 防止超长标签撑爆界面
            n = n[:12]
        seen.add(n)
        result.append(n)
    return result


def parse_tag_input(text):
    """把「入门, 面试必备，经典」这类输入解析成标签列表（支持中英文逗号与顿号）"""
    if not text:
        return []
    for sep in ("，", "、", ";", "；"):
        text = text.replace(sep, ",")
    return _clean(text.split(","))


def get_or_create_tag(cur, name):
    """内部函数：取标签 id，不存在则创建。需传入已打开的 cursor"""
    cur.execute("SELECT id FROM tag WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO tag(name) VALUES (?)", (name,))
    return cur.lastrowid


def set_book_tags(book_id, tag_names):
    """覆盖式设置某本书的标签
    :param tag_names: 标签名列表或逗号分隔字符串
    :return: (ok: bool, tags: list, msg: str) tags 为最终生效的标签
    """
    names = parse_tag_input(tag_names) if isinstance(tag_names, str) else _clean(tag_names)
    init_tag_table()          # 确保表存在，模块可独立调用
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM book WHERE id = ?", (book_id,))
        if not cur.fetchone()[0]:
            return False, [], "图书不存在"

        cur.execute("DELETE FROM book_tag WHERE book_id = ?", (book_id,))
        for name in names:
            tid = get_or_create_tag(cur, name)
            cur.execute("INSERT OR IGNORE INTO book_tag(book_id, tag_id) VALUES (?, ?)",
                        (book_id, tid))
        conn.commit()
        return True, names, "标签已保存"
    except Exception as e:
        print("设置标签异常：", e)
        return False, [], f"设置失败：{e}"
    finally:
        conn.close()


def add_book_tags(book_id, tag_names):
    """给图书追加标签（保留原有标签）"""
    old = get_book_tags(book_id)
    names = parse_tag_input(tag_names) if isinstance(tag_names, str) else _clean(tag_names)
    merged = _clean(old + names)
    return set_book_tags(book_id, merged)


def remove_book_tag(book_id, tag_name):
    """移除某本书的单个标签"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('''
            DELETE FROM book_tag WHERE book_id = ?
              AND tag_id = (SELECT id FROM tag WHERE name = ?)
        ''', (book_id, tag_name))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print("移除标签异常：", e)
        return False
    finally:
        conn.close()


def _tables_ready(cur):
    """检查标签相关表是否已创建（未建表时查询函数应优雅降级而不是崩溃）"""
    cur.execute("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE type = 'table' AND name IN ('tag', 'book_tag')
    """)
    return (cur.fetchone()[0] or 0) == 2


def get_book_tags(book_id):
    """取某本书的标签名列表"""
    conn = get_conn()
    cur = conn.cursor()
    if not _tables_ready(cur):
        conn.close()
        return []
    cur.execute('''
        SELECT t.name FROM book_tag bt
        LEFT JOIN tag t ON bt.tag_id = t.id
        WHERE bt.book_id = ? ORDER BY t.name
    ''', (book_id,))
    tags = [r[0] for r in cur.fetchall()]
    conn.close()
    return tags


def get_tags_map():
    """批量取所有图书的标签：{book_id: [标签名, ...]}"""
    conn = get_conn()
    cur = conn.cursor()
    if not _tables_ready(cur):
        conn.close()
        return {}
    cur.execute('''
        SELECT bt.book_id, t.name FROM book_tag bt
        LEFT JOIN tag t ON bt.tag_id = t.id
        ORDER BY bt.book_id, t.name
    ''')
    data = {}
    for bid, name in cur.fetchall():
        data.setdefault(bid, []).append(name)
    conn.close()
    return data


def get_all_tags():
    """全部标签及其使用图书数，按使用数降序
    :return: [(标签名, 图书数), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    if not _tables_ready(cur):
        conn.close()
        return []
    cur.execute('''
        SELECT t.name, COUNT(bt.book_id) c
        FROM tag t
        LEFT JOIN book_tag bt ON bt.tag_id = t.id
        GROUP BY t.id, t.name
        ORDER BY c DESC, t.name
    ''')
    rows = cur.fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def get_books_by_tags(tag_names, match_all=False):
    """按标签筛选图书
    :param tag_names: 标签名列表或逗号分隔字符串
    :param match_all: True=必须同时具备全部标签；False=具备任一即可
    :return: [(id,title,author,category,is_borrow), ...]
    """
    names = parse_tag_input(tag_names) if isinstance(tag_names, str) else _clean(tag_names)
    conn = get_conn()
    cur = conn.cursor()
    try:
        # 不给标签时等价于「查看全部图书」
        if not names:
            cur.execute("SELECT id,title,author,category,is_borrow FROM book ORDER BY id")
            return cur.fetchall()
        if not _tables_ready(cur):
            return []

        placeholders = ",".join("?" * len(names))
        if match_all:
            # 图书必须同时具备全部指定标签
            sql = f'''
                SELECT b.id, b.title, b.author, b.category, b.is_borrow
                FROM book b
                WHERE b.id IN (
                    SELECT bt.book_id FROM book_tag bt
                    LEFT JOIN tag t ON bt.tag_id = t.id
                    WHERE t.name IN ({placeholders})
                    GROUP BY bt.book_id
                    HAVING COUNT(DISTINCT t.name) = ?
                )
                ORDER BY b.id
            '''
            cur.execute(sql, names + [len(names)])
        else:
            # 具备任一标签即可
            sql = f'''
                SELECT DISTINCT b.id, b.title, b.author, b.category, b.is_borrow
                FROM book b
                JOIN book_tag bt ON b.id = bt.book_id
                LEFT JOIN tag t ON bt.tag_id = t.id
                WHERE t.name IN ({placeholders})
                ORDER BY b.id
            '''
            cur.execute(sql, names)
        return cur.fetchall()
    except Exception as e:
        print("按标签筛选异常：", e)
        return []
    finally:
        conn.close()


def delete_tag(tag_name):
    """删除一个标签（同时解绑所有图书）"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM book_tag WHERE tag_id = (SELECT id FROM tag WHERE name = ?)", (tag_name,))
        cur.execute("DELETE FROM tag WHERE name = ?", (tag_name,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print("删除标签异常：", e)
        return False
    finally:
        conn.close()


def get_tag_stat():
    """标签统计：总数、已被使用的标签数、关联关系数"""
    conn = get_conn()
    cur = conn.cursor()
    if not _tables_ready(cur):
        conn.close()
        return {"total": 0, "used": 0, "links": 0, "tagged_books": 0}
    total = cur.execute("SELECT COUNT(*) FROM tag").fetchone()[0]
    used = cur.execute("SELECT COUNT(DISTINCT tag_id) FROM book_tag").fetchone()[0]
    links = cur.execute("SELECT COUNT(*) FROM book_tag").fetchone()[0]
    tagged_books = cur.execute("SELECT COUNT(DISTINCT book_id) FROM book_tag").fetchone()[0]
    conn.close()
    return {"total": total, "used": used, "links": links, "tagged_books": tagged_books}


if __name__ == "__main__":
    init_tag_table()
    print("tag 模块加载完成")
    print("标签统计:", get_tag_stat())
