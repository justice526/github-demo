"""用户数据访问层

只写 SQL。密码策略、密保校验、余额规则等属于 service 层。

表归属：本模块独占 `user` 表。其他模块需要用户名时走
`get_username()`，而不是自己去 JOIN user 表 —— 这样表归属清晰，
将来换表或加缓存只改这一处。
"""

from core import db


def _to_tuple(row):
    return tuple(row) if row is not None else None


def _to_tuples(rows):
    return [tuple(r) for r in rows]


# ==================== 读 ====================

def find_by_username(username):
    """按用户名查全字段（登录用），不存在返回 None"""
    return _to_tuple(db.query_one(
        "SELECT id, username, password, balance, is_admin FROM user WHERE username = ?",
        (username,)))


def get_username(user_id):
    """按 ID 取用户名（供 log 模块拼日志用）"""
    row = db.query_one("SELECT username FROM user WHERE id = ?", (user_id,))
    return row[0] if row else None


def exists_username(username):
    """用户名是否已被占用"""
    return db.query_one("SELECT 1 FROM user WHERE username = ?", (username,)) is not None


def get_balance(user_id):
    """余额；用户不存在返回 0.0"""
    row = db.query_one("SELECT balance FROM user WHERE id = ?", (user_id,))
    return row[0] if row else 0.0


def is_admin(user_id):
    """是否管理员；用户不存在返回 False"""
    row = db.query_one("SELECT is_admin FROM user WHERE id = ?", (user_id,))
    return bool(row and row[0])


def get_security_answer(username):
    """取密保问题与答案（找回密码用）"""
    row = db.query_one(
        "SELECT security_q, security_a FROM user WHERE username = ?", (username,))
    return (row[0], row[1]) if row else (None, None)


def find_all():
    """全部用户：[(id, username, balance, is_admin), ...]（不含密码）"""
    return _to_tuples(db.query_all(
        "SELECT id, username, balance, is_admin FROM user ORDER BY id"))


def count_all():
    return db.query_one("SELECT COUNT(*) FROM user")[0]


# ==================== 写 ====================

def insert(username, password, balance=0.0, is_admin=0, security_q="", security_a=""):
    """新增用户，返回新用户 ID"""
    with db.transaction() as cur:
        cur.execute(
            """INSERT INTO user(username, password, balance, is_admin, security_q, security_a)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, password, balance, is_admin, security_q, security_a))
        return cur.lastrowid


def update_password(user_id, new_password):
    with db.transaction() as cur:
        cur.execute("UPDATE user SET password=? WHERE id=?", (new_password, user_id))
        return cur.rowcount


def password_matches(user_id, password):
    """校验密码是否匹配（修改密码时用）"""
    return db.query_one("SELECT 1 FROM user WHERE id = ? AND password = ?",
                        (user_id, password)) is not None


def add_balance(user_id, delta):
    """余额增减（delta 可为负），返回操作后余额"""
    with db.transaction() as cur:
        cur.execute("UPDATE user SET balance = balance + ? WHERE id = ?", (delta, user_id))
        row = cur.execute("SELECT balance FROM user WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else 0.0


def deduct_balance_in(cur, user_id, amount):
    """扣减余额，复用调用方事务游标

    缴罚款时「扣钱」与「销罚款」必须原子生效，故提供
    接受外部游标的版本由 user_service 在同一事务内协调。
    """
    cur.execute("UPDATE user SET balance = balance - ? WHERE id = ?", (amount, user_id))
    return cur.rowcount
