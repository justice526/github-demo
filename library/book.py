import sqlite3
import os
import json

def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def add_book(title, author, category):
    """新增图书"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO book(title, author, category, is_borrow) VALUES (?, ?, ?, 0)", (title, author, category))
        conn.commit()
        return True
    except Exception as e:
        print(e)
        return False
    finally:
        conn.close()

def query_all_book():
    """查询全部图书"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id,title,author,category,is_borrow FROM book")
    data = cur.fetchall()
    conn.close()
    return data

def update_book(book_id, new_title, new_author):
    """修改图书信息"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE book SET title=?, author=? WHERE id=?", (new_title, new_author, book_id))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0

def delete_book(book_id):
    """删除图书"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM book WHERE id=?", (book_id,))
    conn.commit()
    cnt = cur.rowcount
    conn.close()
    return cnt > 0

def search_book(keyword):
    """模糊搜索图书"""
    conn = get_conn()
    cur = conn.cursor()
    sql = """SELECT id,title,author,category,is_borrow FROM book
             WHERE title LIKE ? OR author LIKE ?"""
    cur.execute(sql, (f"%{keyword}%", f"%{keyword}%"))
    res = cur.fetchall()
    conn.close()
    return res

def backup_books_json(save_file="book_backup.json"):
    """导出图书数据备份JSON"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id,title,author,category,is_borrow FROM book")
    data = cur.fetchall()
    conn.close()
    book_list = []
    for row in data:
        book_list.append({
            "id": row[0],
            "title": row[1],
            "author": row[2],
            "category": row[3],
            "is_borrow": row[4]
        })
    try:
        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(book_list, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(e)
        return False

def restore_books_json(filename, overwrite=False):
    """从JSON恢复图书
    overwrite=True 清空原有图书再导入；False追加导入
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(e)
        return False
    conn = get_conn()
    cur = conn.cursor()
    if overwrite:
        cur.execute("DELETE FROM book")
    for b in data:
        cur.execute("INSERT INTO book(title,author,category,is_borrow) VALUES (?,?,?,?)",
                    (b["title"], b["author"], b["category"], b["is_borrow"]))
    conn.commit()
    conn.close()
    return True

def batch_import_book_from_txt(txt_file):
    """txt批量导入，一行：书名,作者,分类"""
    success = 0
    fail = 0
    if not os.path.exists(txt_file):
        return success, fail
    conn = get_conn()
    cur = conn.cursor()
    try:
        with open(txt_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) !=3:
                fail +=1
                continue
            t,a,c = parts
            try:
                cur.execute("INSERT INTO book(title, author, category, is_borrow) VALUES (?,?,?,0)",(t,a,c))
                success +=1
            except:
                fail +=1
        conn.commit()
    except Exception as e:
        print(e)
    finally:
        conn.close()
    return success, fail

def get_book_dashboard():
    """统计仪表盘"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM book")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM book WHERE is_borrow=1")
    borrowed = cur.fetchone()[0]
    available = total - borrowed
    cur.execute("SELECT category,COUNT(*) FROM book GROUP BY category")
    cat_info = cur.fetchall()
    conn.close()
    return {
        "total_book": total,
        "borrowed": borrowed,
        "available": available,
        "category_info": cat_info
    }

def get_hot_book_rank(top_n):
    """热门借阅排行榜，统计每本书被借阅次数"""
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    SELECT b.id, b.title, b.author, COUNT(br.id) borrow_count
    FROM book b LEFT JOIN borrow_record br ON b.id = br.book_id
    GROUP BY b.id, b.title, b.author
    ORDER BY borrow_count DESC
    LIMIT ?
    """
    cur.execute(sql, (top_n,))
    res = cur.fetchall()
    conn.close()
    return res

# ========== 新增：图书分类统计 ==========
def get_category_stat():
    """按分类统计：总数量、在架数、借出数"""
    conn = get_conn()
    cur = conn.cursor()
    sql = '''
    SELECT category,
           COUNT(*) AS total,
           SUM(CASE WHEN is_borrow = 0 THEN 1 ELSE 0 END) AS in_stock,
           SUM(CASE WHEN is_borrow = 1 THEN 1 ELSE 0 END) AS borrowed
    FROM book
    GROUP BY category
    '''
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            "category": row[0],
            "total": row[1],
            "in_stock": row[2],
            "borrowed": row[3]
        })
    return result

# ========== 新增：分页查询图书 ==========
def get_books_by_page(page, page_size=5):
    """
    分页浏览图书
    :param page: 页码，从1开始
    :param page_size: 每页显示条数，默认5
    :return: (图书列表, 总条数)
    """
    conn = get_conn()
    cur = conn.cursor()
    offset = (page - 1) * page_size
    cur.execute("SELECT id,title,author,category,is_borrow FROM book LIMIT ? OFFSET ?", (page_size, offset))
    books = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM book")
    total = cur.fetchone()[0]
    conn.close()
    return books, total

if __name__ == "__main__":
    print("book模块加载完成")
