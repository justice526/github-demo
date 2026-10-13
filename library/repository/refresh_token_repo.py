"""刷新令牌数据访问层

刷新令牌长期有效、服务端存储，支持轮换与吊销。表归属本模块独占
`refresh_token`：token 为主键（随机串），user_id 关联用户，expires_at 控制寿命。
"""
import secrets
import time

from core import db


def init_table():
    """幂等建表"""
    with db.transaction() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS refresh_token (
            token       TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )""")


def create(user_id, ttl):
    """创建刷新令牌并返回其字符串；ttl 单位秒"""
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with db.transaction() as cur:
        cur.execute(
            "INSERT INTO refresh_token(token, user_id, expires_at, created_at) "
            "VALUES (?,?,?,?)", (token, user_id, now + int(ttl), now))
    return token


def validate(token):
    """校验刷新令牌：有效且未过期返回 user_id，否则 None（并清理过期项）"""
    if not token:
        return None
    row = db.query_one(
        "SELECT user_id, expires_at FROM refresh_token WHERE token = ?", (token,))
    if not row:
        return None
    uid, exp = row[0], row[1]
    if int(time.time()) > int(exp):
        revoke(token)
        return None
    return uid


def revoke(token):
    """吊销单个刷新令牌"""
    with db.transaction() as cur:
        cur.execute("DELETE FROM refresh_token WHERE token = ?", (token,))


def revoke_all(user_id):
    """吊销某用户全部刷新令牌（如改密码、强制下线）"""
    with db.transaction() as cur:
        cur.execute("DELETE FROM refresh_token WHERE user_id = ?", (user_id,))
