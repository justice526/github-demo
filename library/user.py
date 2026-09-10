import sqlite3
import os
import base64
def get_conn():
    """复用获取数据库连接工具函数"""
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    return conn

def encrypt_pwd(raw_pwd):
    """密码简单加密，教学演示"""
    byte_data = raw_pwd.encode("utf-8")
    return base64.b64encode(byte_data).decode("utf-8")

def decrypt_pwd(enc_pwd):
    """解密密码，登录校验使用"""
    byte_data = enc_pwd.encode("utf-8")
    return base64.b64decode(byte_data).decode("utf-8")

def register_user(username, password):
    """用户注册
    :param username:用户名
    :param password:密码
    :return: True注册成功；False失败（用户名重复/异常）
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        pwd_enc = encrypt_pwd(password)
        # 改动：插入时 balance 默认 0
        cur.execute("INSERT INTO user(username,password,balance) VALUES (?, ?, 0)", (username, pwd_enc))
        conn.commit()
        return True
    except Exception as e:
        print("注册失败：", e)
        return False
    finally:
        conn.close()

def login_user(username, password):
    """用户登录校验
    :return: 成功返回用户id；失败返回None
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id,password FROM user WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        uid, db_enc_pwd = row
        if decrypt_pwd(db_enc_pwd) == password:
            return uid
    return None

def get_balance(user_id):
    """查询用户当前余额"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM user WHERE id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    if res:
        return res[0]
    return 0

def recharge_balance(user_id, money):
    """用户充值
    :param money: 充值金额，必须大于0
    """
    if money <= 0:
        print("充值金额必须大于0！")
        return False
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE user SET balance = balance + ? WHERE id=?", (money, user_id))
    conn.commit()
    conn.close()
    print(f"充值 {money} 元成功！")
    return True

def pay_fine(user_id, fine_amount):
    """缴纳罚款，余额扣钱，清空该用户未结清罚款
    return True缴费成功；False余额不足
    """
    bal = get_balance(user_id)
    if bal < fine_amount:
        print(f"余额不足！当前余额：{bal}元，需要缴纳 {fine_amount}元")
        return False

    conn = get_conn()
    cur = conn.cursor()
    # 扣余额
    cur.execute("UPDATE user SET balance = balance - ? WHERE id=?", (fine_amount, user_id))
    # 把该用户所有未交的penalty清零
    cur.execute("UPDATE borrow_record SET penalty=0 WHERE user_id=? AND penalty>0", (user_id,))
    conn.commit()
    conn.close()
    print(f"成功缴纳罚款 {fine_amount} 元，剩余余额：{bal - fine_amount} 元")
    return True

# 自测代码
if __name__ == "__main__":
    register_user("admin", "123456")
    uid = login_user("admin", "123456")
    if uid:
        print(f"登录成功，用户ID：{uid}")
        # 自测充值
        recharge_balance(uid, 50)
        print("当前余额：", get_balance(uid))
    else:
        print("账号密码错误")
