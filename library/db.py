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
    # 1. 用户表 user：含密保字段与管理员标识 is_admin
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        balance REAL DEFAULT 0,
        security_q TEXT,
        security_a TEXT,
        is_admin INTEGER DEFAULT 0
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
    # 兼容旧库：user 表补密保字段、管理员字段
    user_cols = _cols("user")
    if "security_q" not in user_cols:
        cur.execute("ALTER TABLE user ADD COLUMN security_q TEXT")
    if "security_a" not in user_cols:
        cur.execute("ALTER TABLE user ADD COLUMN security_a TEXT")
    if "is_admin" not in user_cols:
        cur.execute("ALTER TABLE user ADD COLUMN is_admin INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

# 预置图书清单：(书名, 作者, 分类)
SAMPLE_BOOKS = [
    # 计算机
    ("Python编程：从入门到实践", "埃里克·马瑟斯", "计算机"),
    ("数据结构与算法分析", "马克·艾伦", "计算机"),
    ("计算机网络：自顶向下方法", "库罗斯", "计算机"),
    ("深入理解计算机系统", "兰德尔·布莱恩特", "计算机"),
    ("算法导论", "科尔曼", "计算机"),
    ("代码整洁之道", "罗伯特·马丁", "计算机"),
    # 科幻小说
    ("三体", "刘慈欣", "科幻小说"),
    ("流浪地球", "刘慈欣", "科幻小说"),
    ("球状闪电", "刘慈欣", "科幻小说"),
    ("银河帝国：基地", "阿西莫夫", "科幻小说"),
    # 古典文学
    ("红楼梦", "曹雪芹", "古典文学"),
    ("西游记", "吴承恩", "古典文学"),
    ("三国演义", "罗贯中", "古典文学"),
    ("水浒传", "施耐庵", "古典文学"),
    # 现代文学
    ("活着", "余华", "现代文学"),
    ("围城", "钱钟书", "现代文学"),
    ("平凡的世界", "路遥", "现代文学"),
    ("白鹿原", "陈忠实", "现代文学"),
    # 外国文学
    ("百年孤独", "加西亚·马尔克斯", "外国文学"),
    ("月亮与六便士", "毛姆", "外国文学"),
    ("老人与海", "海明威", "外国文学"),
    ("局外人", "加缪", "外国文学"),
    # 历史
    ("人类简史", "尤瓦尔·赫拉利", "历史"),
    ("明朝那些事儿", "当年明月", "历史"),
    ("万历十五年", "黄仁宇", "历史"),
    ("枪炮、病菌与钢铁", "贾雷德·戴蒙德", "历史"),
    # 人工智能
    ("深度学习", "Ian Goodfellow", "人工智能"),
    ("统计学习方法", "李航", "人工智能"),
    ("机器学习", "周志华", "人工智能"),
    ("人工智能：一种现代方法", "罗素", "人工智能"),
    # 电子工程
    ("信号与系统", "奥本海姆", "电子工程"),
    ("模拟电子技术基础", "童诗白", "电子工程"),
    # 经济管理
    ("经济学原理", "曼昆", "经济管理"),
    ("穷查理宝典", "查理·芒格", "经济管理"),
]

def insert_sample_books():
    """批量插入预置测试图书，防止重复导入"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM book")
    if cur.fetchone()[0] > 0:
        print("⚠图书表已有数据，跳过预置图书导入！")
        conn.close()
        return
    for title, author, category in SAMPLE_BOOKS:
        cur.execute("INSERT INTO book(title, author, category, is_borrow) VALUES (?, ?, ?, 0)",
                    (title, author, category))
    conn.commit()
    conn.close()
    print(f"✅ 预置图书导入完成，共 {len(SAMPLE_BOOKS)} 本！")

def insert_default_admin(username="admin", password="admin123", balance=100.0):
    """预置默认管理员账号（已存在则跳过）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM user WHERE username=?", (username,))
    if cur.fetchone():
        print("⚠管理员账号已存在，跳过创建！")
        conn.close()
        return
    cur.execute(
        "INSERT INTO user(username, password, balance, security_q, security_a, is_admin) VALUES (?, ?, ?, ?, ?, 1)",
        (username, password, balance, "管理员初始密保问题", "admin")
    )
    conn.commit()
    conn.close()
    print(f"✅ 默认管理员创建完成（用户名：{username}  密码：{password}）")

if __name__ == "__main__":
    init_db()
    insert_sample_books()
    insert_default_admin()
    print("数据库初始化完成")
