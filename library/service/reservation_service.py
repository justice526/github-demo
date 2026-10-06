"""预约业务服务层

承载预约状态机与队列推进规则。

状态机::

    reserve ──► waiting ──(归还时)──► ready ──(本人借走)──► done
                  │                      │
                  └──(取消)──► cancelled ◄┘(取消)

关键规则：**只有图书归还时才推进队列**。
借走图书不推进 —— 书仍处于借出状态，通知无意义。
"""

from datetime import datetime

from repository import (book_repo, borrow_repo, reservation_repo,
                        user_repo)


def _book_title(book_id):
    t = book_repo.get_title(book_id)
    return t if t is not None else f"#{book_id}"


def reserve(user_id, book_id):
    """预约图书

    :return: (ok, msg)
    """
    book = book_repo.find_by_id(book_id)
    if not book:
        return False, "图书不存在"
    _, title, _, _, is_borrow = book
    if is_borrow != 1:
        return False, f"《{title}》当前在架可借，无需预约"

    existing = reservation_repo.get_status(user_id, book_id)
    if existing in ("waiting", "ready"):
        return False, f"你已预约过《{title}》，请勿重复预约"

    # 自己已持有这本书就不必预约
    if borrow_repo.find_active_by_user_book(user_id, book_id):
        return False, f"你已借阅《{title}》，无需预约"

    reservation_repo.insert(user_id, book_id)
    pos = queue_position(user_id, book_id)
    if pos == 0:
        return False, f"《{title}》已可借阅，请直接借阅"
    return True, f"预约成功！《{title}》当前排在第 {pos} 位"


def cancel(user_id, book_id):
    """取消预约"""
    status = reservation_repo.get_status(user_id, book_id)
    if status is None:
        return False, "没有找到你的预约记录"
    if status in ("done", "cancelled"):
        return False, "该预约已结束，无法取消"
    reservation_repo.set_status(reservation_repo.find_one(user_id, book_id)["id"],
                               reservation_repo.STATUS_CANCELLED)
    return True, f"已取消《{_book_title(book_id)}》的预约"


def my_reservations(user_id, include_history=False):
    """我的预约列表（dict 列表）

    含 book_id，便于前端按书禁用重复预约 / 取消预约。
    """
    return [
        {"id": r[0], "title": r[1], "reserve_time": r[2],
         "status": status_text(r[3]), "notify_time": r[4], "book_id": r[5]}
        for r in reservation_repo.find_by_user(user_id, active_only=not include_history)
    ]


def status_text(s):
    """状态码转中文"""
    return {
        reservation_repo.STATUS_WAITING: "排队中",
        reservation_repo.STATUS_READY: "已到书待取",
        reservation_repo.STATUS_DONE: "已完成",
        reservation_repo.STATUS_CANCELLED: "已取消",
    }.get(s, s or "")


def queue_of(book_id):
    """某书的预约队列（含用户名与状态）"""
    return [
        {"id": r[0], "user_id": r[1], "username": r[2],
         "reserve_time": r[3], "status": status_text(r[4])}
        for r in reservation_repo.queue_of(book_id)
    ]


def reservation_count(book_id):
    """某书预约人数"""
    return reservation_repo.count_active(book_id)


def queue_position(user_id, book_id):
    """我在队列中的位置；0 表示已到书可直接取"""
    if reservation_repo.get_status(user_id, book_id) == reservation_repo.STATUS_READY:
        return 0
    queue = reservation_repo.queue_of(book_id)
    for i, row in enumerate(queue, start=1):
        if row[1] == user_id:
            return i
    return 0


def ready_for_user(user_id):
    """我有哪些书已到书待取"""
    return [
        {"id": r[0], "title": r[1], "book_id": r[2], "notify_time": r[3]}
        for r in reservation_repo.find_ready_for_user(user_id)
    ]


def has_priority_holder(book_id, user_id):
    """是否有人已到书且不是我 —— 决定我能否抢借"""
    holder = reservation_repo.ready_holder(book_id)
    return holder is not None and holder != user_id


# ==================== 队列推进（供 borrow_service 调用）====================

def on_book_returned(book_id):
    """归还后推进队列：队首 waiting → ready

    :return: 被通知的用户名，无人排队返回 None
    """
    if not reservation_repo.table_ready():
        return None
    head = reservation_repo.head_waiting(book_id)
    if not head:
        return None
    res_id, user_id = head
    # datetime 与 user_repo 放在此处导入：user_repo 依赖 core，
    # 顶层统一导入虽无循环，但把"只在通知时才需要"的依赖延后加载更清晰
    reservation_repo.set_status(res_id, reservation_repo.STATUS_READY,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return user_repo.get_username(user_id)


def on_book_borrowed(user_id, book_id):
    """本人借走该书后把自己的预约标记为已完成

    注意：**不推进队列**。书刚被借走仍属借出状态，
    通知下一个排队者去取一本借不出的书没有意义。
    """
    if not reservation_repo.table_ready():
        return
    row = reservation_repo.find_one(user_id, book_id)
    if row and row["status"] in (reservation_repo.STATUS_READY,
                                 reservation_repo.STATUS_WAITING):
        reservation_repo.set_status(row["id"], reservation_repo.STATUS_DONE)
