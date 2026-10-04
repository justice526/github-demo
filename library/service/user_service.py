"""用户与认证业务服务层

承载注册校验、登录、密保校验、余额规则等业务逻辑。
"""

from core import db
from core.errors import (ValidationError, NotFoundError, AuthError,
                         ConflictError, BusinessRuleError)
from repository import user_repo, borrow_repo

MIN_PASSWORD_LEN = 6
MIN_RECHARGE = 1.0


def register(username, password, security_q="", security_a=""):
    """注册新用户

    :return: 新用户 ID
    :raises ValidationError: 用户名/密码不合规
    :raises ConflictError: 用户名已存在
    """
    username = (username or "").strip()
    password = password or ""
    if not username:
        raise ValidationError("用户名不能为空")
    if len(username) > 20:
        raise ValidationError("用户名不能超过 20 个字符")
    if not password:
        raise ValidationError("密码不能为空")
    if len(password) < MIN_PASSWORD_LEN:
        raise ValidationError(f"密码至少 {MIN_PASSWORD_LEN} 位")
    if user_repo.exists_username(username):
        raise ConflictError(f"用户名「{username}」已被注册")
    return user_repo.insert(username, password, 0.0, 0, security_q, security_a)


def login(username, password):
    """登录校验

    :return: 用户 ID
    :raises AuthError: 账号或密码错误
    """
    row = user_repo.find_by_username((username or "").strip())
    if not row or row[2] != password:
        raise AuthError("账号或密码错误")
    return row[0]


def get_balance(user_id):
    """余额"""
    return user_repo.get_balance(user_id)


def recharge(user_id, money):
    """充值

    :raises ValidationError: 金额非法
    """
    try:
        amount = float(money)
    except (TypeError, ValueError) as e:
        raise ValidationError("充值金额必须是数字") from e
    if amount <= 0:
        raise ValidationError("充值金额必须大于 0")
    if amount > 10000:
        raise ValidationError("单次充值不能超过 10000 元")
    user_repo.add_balance(user_id, amount)
    return True


def pay_fine(user_id, amount):
    """缴纳罚款：扣余额并结清该用户全部未缴罚款

    **原子性**：扣钱与结清必须同时成功或同时失败。
    旧实现分两次 commit，中途失败会「钱扣了但罚款没销」。

    :raises BusinessRuleError: 余额不足
    """
    try:
        amt = float(amount)
    except (TypeError, ValueError) as e:
        raise ValidationError("罚款金额必须是数字") from e
    if amt <= 0:
        raise ValidationError("缴纳金额必须大于 0")
    if user_repo.get_balance(user_id) < amt:
        raise BusinessRuleError(f"余额不足，需缴纳 {amt} 元")

    # 单事务：扣余额 + 结清罚款（SQL 均在 repo 层）
    with db.transaction() as cur:
        user_repo.deduct_balance_in(cur, user_id, amt)
        borrow_repo.clear_penalty_by_user_in(cur, user_id)
    return True


def modify_password(user_id, old_pwd, new_pwd):
    """修改密码

    :raises AuthError: 原密码错误
    :raises ValidationError: 新密码不合规
    """
    if not new_pwd or len(new_pwd) < MIN_PASSWORD_LEN:
        raise ValidationError(f"新密码至少 {MIN_PASSWORD_LEN} 位")
    if not user_repo.password_matches(user_id, old_pwd):
        raise AuthError("原密码不正确")
    user_repo.update_password(user_id, new_pwd)
    return True


def get_security_question(username):
    """取密保问题"""
    q, _ = user_repo.get_security_answer((username or "").strip())
    return q


def reset_password_by_qa(username, security_ans, new_pwd):
    """通过密保重置密码"""
    if not new_pwd or len(new_pwd) < MIN_PASSWORD_LEN:
        raise ValidationError(f"新密码至少 {MIN_PASSWORD_LEN} 位")
    q, a = user_repo.get_security_answer((username or "").strip())
    if q is None:
        raise NotFoundError("用户不存在")
    if not a:
        raise BusinessRuleError("该用户未设置密保问题")
    if (a or "").strip() != (security_ans or "").strip():
        raise AuthError("密保答案不正确")
    row = user_repo.find_by_username(username.strip())
    user_repo.update_password(row[0], new_pwd)
    return True


def is_admin(user_id):
    """是否管理员"""
    return user_repo.is_admin(user_id)


def list_users():
    """全部用户（不含密码）"""
    return user_repo.find_all()
