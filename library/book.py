import sqlite3
import os

def get_conn():
    """获取数据库连接，封装成工具函数"""
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    return conn

def add_book(title, author):
    """新增图书
    :param title: 图书名称
    :param author: 作者
    :return: True成功 / False失败
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO book(title, author) VALUES (?, ?)", (title, author))
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

# 自测入口
if __name__ == "__main__":
    # 测试新增
    add_book("Python编程入门", "张三")
    add_book("SQLite实战", "李四")
    print("所有图书：")
    books = query_all_book()
    for b in books:
        print(b)
