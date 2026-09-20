import sqlite3
import os

def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def register_user(username, password):
    """注册用户，用户名唯一，成功返回True，重复返回False"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO user(username, password, balance) VALUES (?, ?, 0)", (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # 用户名唯一冲突
        return False
    finally:
        conn.close()

def login_user(username, password):
    """登录，成功返回user_id，失败返回None"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM user WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        return None

def get_balance(user_id):
    """查询用户余额"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM user WHERE id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    if res:
        return round(res[0], 2)
    return 0.0

def recharge_balance(user_id, money):
    """余额充值，money>0才生效"""
    if money <= 0:
        return False
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE user SET balance = balance + ? WHERE id=?", (money, user_id))
    conn.commit()
    conn.close()
    return True

def pay_fine(user_id, amount):
    """缴纳罚款：余额扣钱"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM user WHERE id=?", (user_id,))
    bal = cur.fetchone()[0]
    if bal < amount:
        conn.close()
        return False
    # 扣除余额
    cur.execute("UPDATE user SET balance = balance - ? WHERE id=?", (amount, user_id))
    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    # 自测代码
    print("user模块加载完成")