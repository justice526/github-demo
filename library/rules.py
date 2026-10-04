"""借阅规则模块（向后兼容适配层）

业务逻辑在 `service/rules_service.py` 与 `service/borrow_service.py`。
"""

from core.db import get_conn          # 兼容旧的 from rules import get_conn
from repository import rules_repo
from service import rules_service
from service.borrow_service import (check_permission as _check,
                                    fmt_num, get_borrow_limit as _limit,
                                    get_borrow_summary as _summary,
                                    get_fine_threshold as _threshold)
from service.borrow_service import BORROW_DAYS, PENALTY_PER_DAY

# 规则默认值（供外部引用）
DEFAULT_BORROW_LIMIT = rules_repo.DEFAULT_BORROW_LIMIT
DEFAULT_FINE_THRESHOLD = rules_repo.DEFAULT_FINE_THRESHOLD


def init_rules_table():
    """创建 config 参数表（幂等）"""
    rules_repo.init_table()
    return True


# ========== 参数读写 ==========

def get_config(key, default=None):
    """读取一个配置项，不存在时返回 default"""
    return rules_service.get_config(key, default)


def set_config(key, value):
    """写入一个配置项（存在则覆盖）"""
    return rules_service.set_config(key, value)


def get_borrow_limit():
    """每人同时可借阅的册数上限"""
    return _limit()


def set_borrow_limit(n):
    """设置借阅上限，成功返回 True"""
    try:
        rules_service.set_borrow_limit(n)
        return True
    except Exception:
        return False


def get_fine_threshold():
    """欠费停借阈值（0 表示不限制）"""
    return _threshold()


def set_fine_threshold(v):
    """设置欠费阈值，成功返回 True"""
    try:
        rules_service.set_fine_threshold(v)
        return True
    except Exception:
        return False


# ========== 借阅状态与校验 ==========

def get_borrow_summary(user_id):
    """汇总某用户的借阅状态
    :return: dict，含 borrowed/overdue/unpaid_fine/limit/remaining/fine_threshold
    """
    return _summary(user_id)


def check_borrow_permission(user_id):
    """校验借阅资格 :return: (allowed, reason)"""
    return _check(user_id)


def get_borrow_rule_text():
    """把当前规则拼成一句可展示的说明（沿用旧版单行文案）"""
    limit = get_borrow_limit()
    threshold = get_fine_threshold()
    return (f"借阅规则：每人同时最多借 {limit} 本；"
            f"有逾期未还图书时暂停借阅；未结清罚款达 {fmt_num(threshold)} 元时暂停借阅；"
            f"借期 {BORROW_DAYS} 天，逾期每天 {PENALTY_PER_DAY} 元。")


def get_rule_config():
    """返回全部规则参数（供设置界面回填）"""
    return rules_service.rule_config()


if __name__ == "__main__":
    init_rules_table()
    print("rules 模块为兼容适配层，业务逻辑见 service/rules_service.py")
