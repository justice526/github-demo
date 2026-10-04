"""操作日志模块（向后兼容适配层）

业务逻辑在 `service/log_service.py`。

**写日志失败绝不影响主业务** —— 这一点在 service 层用
try/except 保证，本适配层直接透传返回值。
"""

from core.db import get_conn          # 兼容旧的 from log import get_conn
from repository import log_repo
from service import log_service

# 动作码 → 中文（供 GUI 下拉框直接使用）
ACTION_TEXT = dict(log_service.ACTION_TEXT)


def action_text(code):
    """动作码转中文"""
    return log_service.action_text(code)


def init_log_table():
    """创建操作日志表（幂等）"""
    log_repo.init_table()
    return True


def write_log(user_id, action, target="", detail=""):
    """写一条操作日志；失败返回 False 而不抛异常"""
    return log_service.write(user_id, action, target, detail)


def get_logs(limit=100, action=None, user_id=None):
    """查询操作日志（倒序）
    :return: [(ID, 用户名, 动作, 对象, 详情, 时间), ...]
    """
    return [
        (r["id"], r["username"], r["action"], r["target"],
         r["detail"], r["log_time"])
        for r in log_service.query(limit, action, user_id)
    ]


def get_action_stats():
    """各动作计数 :return: [(动作代码, 中文名, 次数), ...]"""
    return log_service.action_stats()


def get_log_count():
    """日志总条数"""
    return log_service.count()


def clear_logs():
    """清空操作日志，返回清空条数"""
    return log_repo.clear_all()


if __name__ == "__main__":
    print("log 模块为兼容适配层，业务逻辑见 service/log_service.py")
