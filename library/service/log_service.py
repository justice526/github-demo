"""操作日志业务服务层

**核心约束：写日志是附加价值，失败绝不能影响主业务。**
`write()` 内部吞掉所有异常并返回 False，调用方无需 try/except。
"""

from repository import log_repo, user_repo

# 动作码 → 中文文案
ACTION_TEXT = {
    "register": "注册",
    "login": "登录",
    "logout": "退出",
    "borrow": "借阅",
    "return": "归还",
    "renew": "续借",
    "recharge": "充值",
    "pay_fine": "缴纳罚款",
    "rate": "评分",
    "unrate": "撤销评分",
    "reserve": "预约",
    "cancel_reserve": "取消预约",
    "add_book": "新增图书",
    "update_book": "修改图书",
    "delete_book": "删除图书",
    "set_tag": "设置标签",
    "import_book": "批量导入",
    "export": "导出数据",
    "backup": "备份数据",
    "restore": "恢复数据",
}


def action_text(code):
    """动作码转中文"""
    return ACTION_TEXT.get(code, code or "")


def write(user_id, action, target="", detail=""):
    """写一条操作日志

    :return: True 成功 / False 失败（**失败不影响主流程**）
    """
    try:
        if not log_repo.table_ready():
            return False
        # 用户名从 user_repo 取，日志模块自己不查 user 表
        username = user_repo.get_username(user_id) if user_id is not None else None
        log_repo.insert(user_id, username, action, target, detail)
        return True
    except Exception as e:
        # 写日志失败只打印，绝不向上抛 —— 主业务优先级更高
        print("写操作日志异常：", e)
        return False


def query(limit=100, action=None, user_id=None):
    """查询日志：[{id, username, action, action_text, target, detail, log_time}]"""
    return [
        {"id": r[0], "username": r[1], "action": r[2],
         "action_text": action_text(r[2]), "target": r[3],
         "detail": r[4], "log_time": r[5]}
        for r in log_repo.find_logs(limit, action, user_id)
    ]


def action_stats():
    """动作计数：[(动作码, 中文, 次数)]，按次数降序"""
    return [(r[0], action_text(r[0]), r[1]) for r in log_repo.action_stats()]


def count():
    """日志总条数"""
    return log_repo.count_all()


def clear():
    """清空全部日志

    与 write() 一致：表不存在时也不应抛异常（可能是尚未初始化的库）。
    """
    if not log_repo.table_ready():
        return True, "没有需要清空的日志"
    n = log_repo.clear_all()
    return True, f"已清空 {n} 条操作日志" if n else "没有需要清空的日志"
