"""图书预约模块（向后兼容适配层）

业务逻辑在 `service/reservation_service.py`。

**队列推进的关键规则**（重构时曾遗漏，此处保留并有测试守护）：
- 归还图书时才把队首 waiting 提升为 ready
- 借走图书**不**推进队列（书仍属借出状态）
"""

from core.db import get_conn          # 兼容旧的 from reservation import get_conn
from repository import reservation_repo
from service import reservation_service
from service import log_service

# 状态常量
WAITING = reservation_repo.STATUS_WAITING
READY = reservation_repo.STATUS_READY
DONE = reservation_repo.STATUS_DONE
CANCELLED = reservation_repo.STATUS_CANCELLED


def init_reservation_table():
    """创建预约表（幂等）"""
    reservation_repo.init_table()
    return True


def reserve_book(user_id, book_id):
    """预约一本已被借出的图书 :return: (ok, msg)"""
    ok, msg = reservation_service.reserve(user_id, book_id)
    if ok:
        log_service.write(user_id, "reserve", f"图书#{book_id}", "预约图书")
    return ok, msg


def cancel_reservation(user_id, book_id):
    """取消预约 :return: (ok, msg)"""
    ok, msg = reservation_service.cancel(user_id, book_id)
    if ok:
        log_service.write(user_id, "cancel_reserve", f"图书#{book_id}", "取消预约")
    return ok, msg


def get_my_reservations(user_id, include_history=False):
    """我的预约列表 [{id, title, reserve_time, status, notify_time}, ...]"""
    return reservation_service.my_reservations(user_id, include_history)


def get_book_queue(book_id):
    """某书的预约队列 [{id, user_id, username, reserve_time, status}, ...]"""
    return reservation_service.queue_of(book_id)


def get_reservation_count(book_id):
    """某书的预约人数"""
    return reservation_service.reservation_count(book_id)


def get_my_queue_position(user_id, book_id):
    """我在队列中的位置；0 表示已到书可直接取"""
    return reservation_service.queue_position(user_id, book_id)


def get_ready_for_user(user_id):
    """我有哪些书已到书待取"""
    return reservation_service.ready_for_user(user_id)


def has_priority_holder(book_id, user_id):
    """是否有人已到书且不是我"""
    return reservation_service.has_priority_holder(book_id, user_id)


# ===== 队列推进（由 borrow_service 在借阅/归还时调用）=====

def on_book_returned(book_id):
    """归还后推进队列：队首 waiting → ready，返回被通知者用户名"""
    return reservation_service.on_book_returned(book_id)


def on_book_borrowed(user_id, book_id):
    """本人借走后把自己的预约标记完成；**不推进队列**"""
    return reservation_service.on_book_borrowed(user_id, book_id)


if __name__ == "__main__":
    print("reservation 模块为兼容适配层，业务逻辑见 service/reservation_service.py")
