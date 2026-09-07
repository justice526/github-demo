import sqlite3
import os

def get_conn():
    """复用获取数据库连接工具函数"""
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    return conn


def register_user(username, password):
    """用户注册
    :param username:用户名
    :param password:密码
    :return: True注册成功；False失败（用户名重复/异常）
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO user(username,password) VALUES (?, ?)", (username, password))
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
    cur.execute("SELECT id FROM user WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        return None


# 自测代码
if __name__ == "__main__":
    register_user("admin", "123456")
    uid = login_user("admin", "123456")
    if uid:
        print(f"登录成功，用户ID：{uid}")
    else:
        print("账号密码错误")
