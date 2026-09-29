import sqlite3
import os

def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# ========= 用户相关 =========
def register_user(username, password, security_q="", security_a=""):
    """注册用户，用户名唯一；成功返回True，重复返回False"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO user(username, password, balance, security_q, security_a) VALUES (?, ?, 0, ?, ?)",
                    (username, password, security_q, security_a))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    """登录，成功返回user_id，失败返回None"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM user WHERE username=? AND password=?", (username, password))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else None

def get_balance(user_id):
    """查询用户余额"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM user WHERE id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return round(res[0], 2) if res else 0.0

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

def modify_password(user_id, old_pwd, new_pwd):
    """修改登录密码"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM user WHERE id=? AND password=?", (user_id, old_pwd))
    if not cur.fetchone():
        conn.close()
        return False
    cur.execute("UPDATE user SET password=? WHERE id=?", (new_pwd, user_id))
    conn.commit()
    conn.close()
    return True

# ===== 忘记密码：获取密保问题 =====
def get_security_question(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT security_q FROM user WHERE username=?", (username,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else None

# ===== 忘记密码：验证密保答案，重置密码 =====
def reset_password_by_qa(username, security_ans, new_pwd):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM user WHERE username=? AND security_a=?", (username, security_ans))
    if not cur.fetchone():
        conn.close()
        return False
    cur.execute("UPDATE user SET password=? WHERE username=?", (new_pwd, username))
    conn.commit()
    conn.close()
    return True

# ===== 管理员：判断当前用户是否为管理员 =====
def is_admin(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM user WHERE id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return bool(res and res[0] == 1)

# ===== 管理员：查询全部用户 =====
def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, balance, is_admin FROM user")
    data = cur.fetchall()
    conn.close()
    return data

# ===== 罚款相关 =====
def pay_fine(user_id, amount):
    """缴纳罚款：余额扣钱，并结清该用户所有未缴罚款"""
    conn = get_conn()
    cur = conn.cursor()
    if get_balance(user_id) < amount:
        conn.close()
        return False
    cur.execute("UPDATE user SET balance = balance - ? WHERE id=?", (amount, user_id))
    # 结清该用户所有未缴罚款（penalty > 0 的记录）
    cur.execute("UPDATE borrow_record SET penalty=0 WHERE user_id=? AND penalty > 0", (user_id,))
    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    print("user模块加载完成")
