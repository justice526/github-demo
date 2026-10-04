"""用户模块（向后兼容适配层）

真正的业务逻辑在 `service/user_service.py`。
本文件保持原有函数签名与返回约定，异常在此翻译回旧行为。

适配要点：
- `login_user` 失败返回 None（旧实现如此，不是 False）
- `get_balance` 保留 round(x, 2) 舍入
- 重复注册 / 密码错误等一律返回 False，异常不外泄
"""

from core.errors import AppError
from core.db import get_conn          # 兼容旧的 from user import get_conn
from service import user_service
from service import log_service


# ==================== 注册 / 登录 ====================

def register_user(username, password, security_q="", security_a=""):
    """注册用户，用户名唯一；成功 True，重复或非法返回 False"""
    try:
        uid = user_service.register(username, password, security_q, security_a)
        # 用新用户 id 记日志，与旧实现一致（日志要能追溯到人）
        log_service.write(uid, "register", str(username), "新用户注册")
        return True
    except AppError:
        return False
    except Exception:
        return False


def login_user(username, password):
    """登录，成功返回 user_id，失败返回 None"""
    try:
        uid = user_service.login(username, password)
        log_service.write(uid, "login", str(username), "登录成功")
        return uid
    except AppError:
        return None
    except Exception:
        return None


# ==================== 余额 ====================

def get_balance(user_id):
    """查询用户余额（保留两位小数）"""
    return round(user_service.get_balance(user_id), 2)


def recharge_balance(user_id, money):
    """充值，money > 0 才生效"""
    try:
        user_service.recharge(user_id, money)
        log_service.write(user_id, "recharge", f"用户#{user_id}", f"充值 {money} 元")
        return True
    except AppError:
        return False
    except Exception:
        return False


def pay_fine(user_id, amount):
    """缴纳罚款：扣余额并结清该用户所有未缴罚款"""
    try:
        user_service.pay_fine(user_id, amount)
        log_service.write(user_id, "pay_fine", f"用户#{user_id}", f"缴纳罚款 {amount} 元")
        return True
    except AppError:
        return False
    except Exception:
        return False


# ==================== 密码 ====================

def modify_password(user_id, old_pwd, new_pwd):
    """修改登录密码"""
    try:
        user_service.modify_password(user_id, old_pwd, new_pwd)
        return True
    except AppError:
        return False
    except Exception:
        return False


def get_security_question(username):
    """取密保问题"""
    return user_service.get_security_question(username)


def reset_password_by_qa(username, security_ans, new_pwd):
    """通过密保问题与答案重置密码"""
    try:
        user_service.reset_password_by_qa(username, security_ans, new_pwd)
        return True
    except AppError:
        return False
    except Exception:
        return False


def is_admin(user_id):
    """是否管理员"""
    return user_service.is_admin(user_id)


def get_all_users():
    """全部用户（不含密码）"""
    return user_service.list_users()


if __name__ == "__main__":
    print("user 模块为兼容适配层，业务逻辑见 service/user_service.py")
