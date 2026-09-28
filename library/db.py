import sqlite3
import os

def get_conn():
    """获取数据库连接并开启外键约束"""
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """初始化数据库（自动兼容旧库，缺失字段自动补充）"""
    conn = get_conn()
    cur = conn.cursor()
    # 1. 用户表 user：id 主键，用户名，密码，余额，密保问题/答案
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        balance REAL DEFAULT 0,
        security_q TEXT,
        security_a TEXT
    )
    ''')
    # 2. 图书表 book，含 category 分类字段
    cur.execute('''
    CREATE TABLE IF NOT EXISTS book (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT,
        category TEXT,
        is_borrow INTEGER DEFAULT 0
    )
    ''')
    # 3. 借阅记录表 borrow_record
    cur.execute('''
    CREATE TABLE IF NOT EXISTS borrow_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        book_id INTEGER,
        borrow_time TEXT,
        return_deadline TEXT,
        return_time TEXT,
        penalty REAL DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES user(id),
        FOREIGN KEY(book_id) REFERENCES book(id)
    )
    ''')

    def _cols(table):
        cur.execute(f"PRAGMA table_info({table})")
        return [r[1] for r in cur.fetchall()]

    # 兼容旧库：book 表补 category 列
    if "category" not in _cols("book"):
        cur.execute("ALTER TABLE book ADD COLUMN category TEXT")
    # 兼容旧库：user 表补密保字段
    user_cols = _cols("user")
    if "security_q" not in user_cols:
        cur.execute("ALTER TABLE user ADD COLUMN security_q TEXT")
    if "security_a" not in user_cols:
        cur.execute("ALTER TABLE user ADD COLUMN security_a TEXT")

    conn.commit()
    conn.close()

def insert_sample_books():
    """批量插入预置测试图书，防止重复导入"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM book")
    if cur.fetchone()[0] > 0:
        print("⚠图书表已有数据，跳过预置图书导入！")
        conn.close()
        return

    book_list = [
        ("Python编程：从入门到实践", "埃里克", "计算机"),
        ("数据结构与算法分析", "马克·艾伦", "计算机"),
        ("三体", "刘慈欣", "科幻小说"),
        ("流浪地球", "刘慈欣", "科幻小说"),
        ("红楼梦", "曹雪芹", "古典文学"),
        ("西游记", "吴承恩", "古典文学"),
        ("百年孤独", "马尔克斯", "外国文学"),
        ("人类简史", "赫拉利", "历史"),
        ("明朝那些事儿", "当年明月", "历史"),
        ("深度学习", "Ian Goodfellow", "人工智能"),
        ("统计学习方法", "李航", "人工智能"),
        ("活着", "余华", "现代文学"),
        ("围城", "钱钟书", "现代文学"),
        ("信号与系统", "奥本海姆", "电子工程"),
        ("计算机网络", "谢希仁", "计算机"),
    ]
    for title, author, category in book_list:
        cur.execute("INSERT INTO book(title, author, category, is_borrow) VALUES (?, ?, ?, 0)", (title, author, category))
    conn.commit()
    conn.close()
    print("✅ 预置图书导入完成！")

if __name__ == "__main__":
    init_db()
    insert_sample_books()
    print("数据库初始化完成")
