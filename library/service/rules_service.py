"""规则参数业务服务层

承载借阅规则的读写与文案生成。
统计取数在 rules_repo，参数默认值与展示格式在本层。
"""

from core.errors import ValidationError
from repository import rules_repo
from service.borrow_service import (BORROW_DAYS, check_permission, fmt_num,
                                    get_borrow_summary, get_borrow_limit,
                                    get_fine_threshold)

# 业务常量（供规则面板展示）
DEFAULT_BORROW_LIMIT = rules_repo.DEFAULT_BORROW_LIMIT
DEFAULT_FINE_THRESHOLD = rules_repo.DEFAULT_FINE_THRESHOLD


def get_config(key, default=None):
    """读一个配置项"""
    return rules_repo.get_value(key, default)


def set_config(key, value):
    """写一个配置项"""
    return rules_repo.set_value(key, value)


def set_borrow_limit(n):
    """设置借阅上限

    :raises ValidationError: 超出允许范围
    """
    try:
        v = int(n)
    except (TypeError, ValueError) as e:
        raise ValidationError("借阅上限必须是整数") from e
    if v < 1 or v > 50:
        raise ValidationError("借阅上限需在 1 到 50 之间")
    rules_repo.set_value("borrow_limit", v)
    return v


def set_fine_threshold(v):
    """设置欠费停借阈值（0 表示不限制）"""
    try:
        f = float(v)
    except (TypeError, ValueError) as e:
        raise ValidationError("欠费阈值必须是数字") from e
    if f < 0 or f > 10000:
        raise ValidationError("欠费阈值需在 0 到 10000 之间")
    rules_repo.set_value("fine_threshold", f)
    return f


def rule_config():
    """全部规则参数：{borrow_limit, fine_threshold}"""
    return {
        "borrow_limit": get_borrow_limit(),
        "fine_threshold": get_fine_threshold(),
    }


def rule_text():
    """规则说明文案（供界面展示）"""
    limit = get_borrow_limit()
    thr = get_fine_threshold()
    lines = [f"· 每人同时最多借阅 {limit} 本"]
    lines.append(f"· 借阅期限 {BORROW_DAYS} 天，可续借")
    lines.append("· 有逾期未还图书时暂停借阅")
    if thr > 0:
        lines.append(f"· 累计欠费达到 {fmt_num(thr)} 元时暂停借阅")
    else:
        lines.append("· 欠费不限制借阅（阈值为 0）")
    return "\n".join(lines)
