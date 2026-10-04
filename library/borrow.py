"""借阅模块（向后兼容适配层）

真正的业务逻辑在 `service/borrow_service.py`。

**本文件的核心价值是「精确还原旧返回结构」**。
重构前各函数的 key 名与返回类型并不统一：
- `get_borrow_record` 返回**元组列表**（GUI 表格按列下标取数）
- `get_user_borrow_stats` 用 total_borrow / unreturned / overdue_count
- `get_due_soon_books` 用 remain_days（service 层统一成了 days_left）

这些差异被 gui.py 直接依赖，改名会导致界面拿不到数据，
故适配层在此把 service 的统一结构翻译回旧结构。
"""

from core.db import get_conn          # 兼容旧的 from borrow import get_conn
from repository import book_repo, borrow_repo
from service import borrow_service
from service import log_service


# ==================== 借阅 / 归还 ====================

def borrow_book(user_id, book_id):
    """借阅图书，保留旧的 True/False 语义"""
    ok, _ = borrow_service.borrow_book(user_id, book_id)
    return ok


def borrow_book_ex(user_id, book_id):
    """借阅图书（带规则校验与预约优先权），返回可展示的原因 (ok, msg)"""
    ok, msg = borrow_service.borrow_book(user_id, book_id)
    if ok:
        title = book_repo.get_title(book_id) or ""
        log_service.write(user_id, "borrow", f"《{title}》#{book_id}", msg[:40])
    return ok, msg


def return_book(user_id, book_id):
    """归还图书；返回罚款金额，无未归还记录返回 False"""
    penalty = borrow_service.return_book(user_id, book_id)
    if penalty is not False:
        title = book_repo.get_title(book_id) or ""
        log_service.write(user_id, "return", f"《{title}》#{book_id}", f"罚款 {penalty} 元")
    return penalty


def renew_book(user_id, book_id, add_days=7):
    """续借，返回 (ok, msg)"""
    ok, msg = borrow_service.renew_book(user_id, book_id, add_days)
    if ok:
        title = book_repo.get_title(book_id) or ""
        log_service.write(user_id, "renew", f"《{title}》#{book_id}", f"续借 {add_days} 天")
    return ok, msg


# ==================== 查询 ====================

def get_borrow_record(user_id):
    """某用户全部借阅记录

    返回**元组列表**：(id, title, borrow_time, deadline, return_time, penalty)
    GUI 表格按下标取数，故不能改成 dict。
    """
    return [
        (r["id"], r["title"], r["borrow_time"], r["deadline"],
         r["return_time"], r["penalty"])
        for r in borrow_service.my_records(user_id)
    ]


def get_user_total_penalty(user_id):
    """未结清罚款总和（保留两位小数）"""
    return borrow_service.my_total_penalty(user_id)


def get_user_borrow_stats(user_id):
    """借阅统计概览

    key 名沿用旧版：total_borrow / returned / unreturned /
    total_penalty / overdue_count —— gui.py 依赖这些名字。
    """
    s = borrow_service.my_stats(user_id)
    return {
        "total_borrow": s["total"],
        "returned": s["returned"],
        "unreturned": s["active"],
        "total_penalty": s["unpaid_fine"],
        "overdue_count": s["overdue"],
    }


def get_due_soon_books(user_id, days=3):
    """即将到期（days 天内）且未逾期未归还的图书

    字段名 remain_days 沿用旧版。
    """
    return [
        {
            "record_id": r["record_id"],
            "title": r["title"],
            "deadline": r["deadline"],
            "remain_days": r["days_left"],
        }
        for r in borrow_service.due_soon_books(user_id, days)
    ]


def get_book_borrow_history(book_id, limit=30):
    """某本书的借阅历史 [(id, user_id, borrow_time, deadline, return_time), ...]"""
    return borrow_service.book_history(book_id, limit)


def get_my_current_borrow(user_id, book_id):
    """当前未归还的借阅记录，不存在返回 None"""
    return borrow_repo.find_active_by_user_book(user_id, book_id)


# ==================== 导出 ====================

def export_borrow_record_to_txt(user_id, save_path="borrow_record.txt"):
    """导出借阅记录为 txt"""
    try:
        borrow_service.export_my_txt(user_id, save_path)
        return True
    except OSError:
        return False


def export_borrow_record_to_csv(user_id, save_path="borrow_record.csv"):
    """导出借阅记录为 CSV（utf-8-sig，Excel 不乱码）"""
    try:
        borrow_service.export_my_csv(user_id, save_path)
        return True
    except OSError:
        return False


def export_all_borrow_to_csv(save_path="all_borrow_records.csv"):
    """导出全部借阅记录为 CSV"""
    try:
        borrow_service.export_all_csv(save_path)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    print("borrow 模块为兼容适配层，业务逻辑见 service/borrow_service.py")
