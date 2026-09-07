import sqlite3
import os

def init_db():
    """初始化数据库，创建三张数据表：用户表、图书表、借阅记录表"""
    # 连接SQLite数据库，文件存放在library/library.db
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "library.db"))
    cur = conn.cursor()

    # 1. 用户表 user：id 主键，用户名，密码
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    ''')

    # 2.图书表 book
    cur.execute('''
    CREATE TABLE IF NOT EXISTS book (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT,
        is_borrow INTEGER DEFAULT 0
    )
    ''')

    #3.借阅记录 borrow_record
    cur.execute('''
    CREATE TABLE IF NOT EXISTS borrow_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        book_id INTEGER,
        borrow_time TEXT,
        return_time TEXT,
        FOREIGN KEY(user_id) REFERENCES user(id),
        FOREIGN KEY(book_id) REFERENCES book(id)
    )
    ''')

    conn.commit()  # 提交建表改动到数据库
    conn.close()   # 关闭数据库连接

if __name__ == "__main__":
    init_db()
    print("数据库初始化完成，数据表已创建")
