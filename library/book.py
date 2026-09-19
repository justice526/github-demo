import sqlite3
import os
import json

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
        # 新增图书默认is_borrow=0（未借出，在架）
        cur.execute("INSERT INTO book(title, author, category, is_borrow) VALUES (?, ?, ?, 0)", (title, author, category))
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
    try:
        cur.execute("UPDATE book SET title=?, author=? WHERE id=?", (new_title, new_author, book_id))
        conn.commit()
    except Exception as e:
        print("修改图书异常：", e)
    finally:
        conn.close()

def delete_book(book_id):
    """根据id删除图书"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM book WHERE id=?", (book_id,))
        conn.commit()
    except Exception as e:
        print("删除图书异常：", e)
    finally:
        conn.close()

def query_book_by_category(category_name):
    """根据图书分类名称查询图书"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM book WHERE category = ?", (category_name,))
    result = cur.fetchall()
    conn.close()
    return result

def search_book(keyword):
    """
    模糊搜索图书，匹配书名或者作者
    :param keyword: 搜索关键词
    :return: 查询到的图书列表
    """
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    SELECT id,title,author,category,is_borrow
    FROM book
    WHERE title LIKE ? OR author LIKE ?
    """
    like_word = f"%{keyword}%"
    cur.execute(sql,(like_word,like_word))
    result = cur.fetchall()
    conn.close()
    return result

def batch_import_book_from_txt(file_path):
    """
    读取txt文件，批量导入图书
    txt文件格式：一行一本图书，书名,作者,分类
    示例txt内容：
    西游记,吴承恩,古典文学
    水浒传,施耐庵,古典文学
    :param file_path: txt文件路径
    :return: (成功数量,失败数量)
    """
    success = 0
    fail = 0
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print("读取txt文件异常：", e)
        return 0, 0
    for line in lines:
        line = line.strip()
        # 跳过空行
        if not line:
            continue
        # 按逗号切割：书名,作者,分类
        parts = line.split(",")
        if len(parts) < 3:
            print(f"格式错误跳过该行：{line} 要求：书名,作者,分类")
            fail += 1
            continue
        title = parts[0].strip()
        author = parts[1].strip()
        category = parts[2].strip()
        # 调用新增图书，传入3个参数
        res = add_book(title, author, category)
        if res:
            success += 1
        else:
            fail += 1
    return success, fail

def backup_books_json(save_path="book_backup.json"):
    """备份全部图书数据到json文件
    :param save_path: 备份文件保存路径
    :return: True成功 / False失败
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id,title,author,category,is_borrow FROM book")
        rows = cur.fetchall()
        # 把元组转成字典列表，方便json存储
        book_list = []
        for row in rows:
            book_list.append({
                "id": row[0],
                "title": row[1],
                "author": row[2],
                "category": row[3],
                "is_borrow": row[4]
            })
        with open(save_path,"w",encoding="utf-8") as f:
            json.dump(book_list, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("备份异常：", e)
        return False
    finally:
        conn.close()

def restore_books_json(load_path="book_backup.json", overwrite=False):
    """从json备份恢复图书
    :param load_path: 备份文件路径
    :param overwrite: True清空原有图书；False追加导入
    :return: True成功 / False失败
    """
    if not os.path.exists(load_path):
        print("备份文件不存在！")
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        with open(load_path,"r",encoding="utf-8") as f:
            book_list = json.load(f)
        if overwrite:
            cur.execute("DELETE FROM book")
        for b in book_list:
            cur.execute(
                "INSERT INTO book(title,author,category,is_borrow) VALUES (?,?,?,?)",
                (b["title"], b["author"], b["category"], b["is_borrow"])
            )
        conn.commit()
        return True
    except Exception as e:
        print("恢复异常：", e)
        conn.rollback()
        return False
    finally:
        conn.close()

def get_book_dashboard():
    """获取图书统计仪表盘数据
    return: dict 统计字典
    """
    conn = get_conn()
    cur = conn.cursor()
    # 1 全部图书总数
    cur.execute("SELECT COUNT(*) FROM book")
    total = cur.fetchone()[0]
    # 2 已借出 is_borrow=1
    cur.execute("SELECT COUNT(*) FROM book WHERE is_borrow=1")
    borrowed = cur.fetchone()[0]
    # 3 在架图书 is_borrow=0
    cur.execute("SELECT COUNT(*) FROM book WHERE is_borrow=0")
    available = cur.fetchone()[0]
    # 4 按分类统计数量
    cur.execute("SELECT category,COUNT(*) FROM book GROUP BY category")
    category_count = cur.fetchall()
    conn.close()
    result = {
        "total_book": total,
        "borrowed": borrowed,
        "available": available,
        "category_info": category_count
    }
    return result

def get_hot_book_rank(top_n=5):
    """
    获取热门借阅图书排行榜
    :param top_n: 取前N名，默认Top5
    :return: list[(图书id,书名,作者,借阅次数)]，失败返回空列表
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        # 关联borrow表和book表，统计每本书借阅次数，按次数降序
        sql = """
        SELECT b.id, b.title, b.author, COUNT(br.id) as borrow_cnt
        FROM book b
        LEFT JOIN borrow br ON b.id = br.book_id
        GROUP BY b.id, b.title, b.author
        ORDER BY borrow_cnt DESC
        LIMIT ?
        """
        cur.execute(sql, (top_n,))
        rows = cur.fetchall()
        return rows
    except Exception as e:
        print("查询热门图书失败：", e)
        return []
    finally:
        conn.close()

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
    # 测试图书统计仪表盘
    dash = get_book_dashboard()
    print("\n====📊仪表盘自测输出====")
    print(f"总图书：{dash['total_book']}")
    print(f"已借出：{dash['borrowed']}")
    print(f"在架：{dash['available']}")
    for cat, num in dash["category_info"]:
        print(f"{cat}:{num}本")
