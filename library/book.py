import sqlite3
import os
def get_conn():
    """获取数据库连接，封装成工具函数"""
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    return conn

def add_book(title, author, category):
    """新增图书
    :param title: 图书名称
    :param author: 作者
    :param category: 图书分类，如 小说、技术
    :return: True成功 / False失败
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO book(title, author, category) VALUES (?, ?, ?)", (title, author, category))
        conn.commit()
        return True
    except Exception as e:
        print("新增图书异常：", e)
        return False
    finally:
        conn.close()

def query_all_book():
    """查询全部图书"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM book")
    result = cur.fetchall()
    conn.close()
    return result

def update_book(book_id, new_title, new_author):
    """修改图书信息
    :param book_id: 图书id
    :param new_title: 新书名
    :param new_author: 新作者
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE book SET title=?, author=? WHERE id=?", (new_title, new_author, book_id))
    conn.commit()
    conn.close()

def delete_book(book_id):
    """根据id删除图书"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM book WHERE id=?", (book_id,))
    conn.commit()
    conn.close()

def query_book_by_category(category_name):
    """根据图书分类名称查询图书"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM book WHERE category = ?", (category_name,))
    result = cur.fetchall()
    conn.close()
    return result

# 自测入口
if __name__ == "__main__":
    # 测试新增，第三个参数传分类
    add_book("Python编程入门", "张三", "技术")
    add_book("SQLite实战", "李四", "技术")
    add_book("三体", "刘慈欣", "科幻")
    print("所有图书：")
    books = query_all_book()
    for b in books:
        print(b)

    print("\n===查询【技术】分类书籍===")
    tech_books = query_book_by_category("技术")
    for b in tech_books:
        print(b)
