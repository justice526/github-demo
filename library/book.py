import sqlite3
import os
import json
from datetime import datetime, timedelta

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
    """删除图书（安全校验：存在未归还借阅则禁止删除）
    :return: True成功；False失败
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        # 先检查是否有未归还的借阅记录
        cur.execute('''
            SELECT COUNT(*) FROM borrow_record
            WHERE book_id = ? AND return_time IS NULL
        ''', (book_id,))
        borrow_cnt = cur.fetchone()[0]
        if borrow_cnt > 0:
            print("删除失败：该图书存在未归还的借阅记录")
            return False
        
        cur.execute("DELETE FROM book WHERE id=?", (book_id,))
        conn.commit()
        cnt = cur.rowcount
        return cnt > 0
    except Exception as e:
        print("删除图书异常：", e)
        return False
    finally:
        conn.close()

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

# ========== 图书分类统计 ==========
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

# ========== 分页查询图书 ==========
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

# ========== 查询用户逾期未还图书 ==========
def get_my_overdue_books(user_id):
    """
    查询当前用户所有逾期未归还的图书
    :param user_id: 用户ID
    :return: list[dict] 逾期图书列表
    """
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    sql = '''
        SELECT br.id, b.title, br.borrow_time, br.return_deadline
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ? AND br.return_time IS NULL
    '''
    cur.execute(sql, (user_id,))
    rows = cur.fetchall()
    conn.close()
    
    overdue_list = []
    for row in rows:
        deadline = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S")
        if now > deadline:
            delta_days = (now - deadline).total_seconds() / (24 * 3600)
            penalty = round(delta_days * 0.5, 2)
            overdue_list.append({
                "record_id": row[0],
                "title": row[1],
                "borrow_time": row[2],
                "deadline": row[3],
                "overdue_days": round(delta_days, 1),
                "current_penalty": penalty
            })
    return overdue_list

# ========== 图书续借 ==========
def renew_book(user_id, book_id, add_days=7):
    """
    续借图书，在原截止时间基础上延长借阅期限
    :param user_id: 用户ID
    :param book_id: 图书ID
    :param add_days: 续借天数，默认7天
    :return: 成功返回新截止时间字符串，失败返回False
    """
    conn = get_conn()
    cur = conn.cursor()
    # 查询该用户这本未归还的借阅记录
    cur.execute('''
        SELECT return_deadline FROM borrow_record
        WHERE user_id = ? AND book_id = ? AND return_time IS NULL
    ''', (user_id, book_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    
    # 原截止时间基础上增加天数
    old_deadline = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    new_deadline = old_deadline + timedelta(days=add_days)
    new_deadline_str = new_deadline.strftime("%Y-%m-%d %H:%M:%S")
    
    # 更新截止时间
    cur.execute('''
        UPDATE borrow_record
        SET return_deadline = ?
        WHERE user_id = ? AND book_id = ? AND return_time IS NULL
    ''', (new_deadline_str, user_id, book_id))
    conn.commit()
    conn.close()
    return new_deadline_str

# ========== 新增：排序查询图书 ==========
def get_books_sorted(sort_by="id", order="asc"):
    """
    排序查询全部图书
    :param sort_by: 排序字段 id/title/author/category
    :param order: 排序方式 asc升序 / desc降序
    :return: 排序后的图书列表
    """
    conn = get_conn()
    cur = conn.cursor()
    # 字段白名单校验，防止SQL注入
    allow_fields = ["id", "title", "author", "category"]
    allow_order = ["asc", "desc"]
    if sort_by not in allow_fields:
        sort_by = "id"
    if order.lower() not in allow_order:
        order = "asc"
    try:
        sql = f"SELECT id,title,author,category,is_borrow FROM book ORDER BY {sort_by} {order}"
        cur.execute(sql)
        res = cur.fetchall()
        return res
    except Exception as e:
        print("排序查询异常：", e)
        return []
    finally:
        conn.close()

if __name__ == "__main__":
    print("book模块加载完成")
