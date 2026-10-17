"""通知聚合服务层

把分散在预约 / 借阅里的「需要用户关注」的状态，聚合成一个统一的通知列表，
供前端轮询展示（铃铛红点）。通知分三类，按紧迫度排序：

- overdue  逾期未还（最紧迫）
- due_soon 即将到期
- ready    预约到书待取

每个通知都有稳定 key（见 notification_repo），用于「已读」状态追踪。
通知是即时计算出来的，不落业务表，保证状态变化立即反映到下一次轮询。
"""

from repository import (notification_repo, reservation_repo)
from service import borrow_service


# 类型排序权重：数字越小越靠前（越紧迫）
_TYPE_WEIGHT = {"overdue": 0, "due_soon": 1, "ready": 2}


def _key_of(ntype, ident):
    return "%s:%s" % (ntype, ident)


def build(user_id):
    """聚合当前用户的全部通知，带已读标记与排序。

    :return: {"items": [...], "unread": int}
        items 中每条：{key, type, title, detail, ts, read}
    """
    raw = []

    # 1) 预约到书待取
    for r in reservation_repo.find_ready_for_user(user_id):
        # r = (id, title, book_id, notify_time)
        res_id, title, _book_id, notify_time = r[0], r[1], r[2], r[3]
        key = _key_of("ready", res_id)
        raw.append({
            "key": key,
            "type": "ready",
            "title": "《%s》已到馆" % title,
            "detail": "你预约的图书已到书，请尽快到馆借阅办理手续",
            "ts": notify_time or "",
        })

    # 2) 即将到期（未逾期、且距到期 <= 默认窗口）
    for b in borrow_service.due_soon_books(user_id, days=3):
        key = _key_of("due", b["record_id"])
        raw.append({
            "key": key,
            "type": "due_soon",
            "title": "《%s》即将到期" % b["title"],
            "detail": "还剩 %.1f 天到期，应还时间 %s" % (b["days_left"], b["deadline"][:16]),
            "ts": b["deadline"],
        })

    # 3) 逾期未还（最紧迫）
    for b in borrow_service.my_overdue_books(user_id):
        key = _key_of("overdue", b["record_id"])
        raw.append({
            "key": key,
            "type": "overdue",
            "title": "《%s》已逾期" % b["title"],
            "detail": "已逾期 %.1f 天，当前罚款 ¥%.2f，请尽快归还" % (
                b["overdue_days"], b["current_penalty"]),
            "ts": b["deadline"],
        })

    # 按紧迫度 + 时间排序（同类型内 ts 倒序：越近的越靠前）
    raw.sort(key=lambda n: (_TYPE_WEIGHT.get(n["type"], 9), n["ts"] or ""))

    # 附加已读状态
    items = []
    unread = 0
    for n in raw:
        read = notification_repo.is_read(user_id, n["key"])
        if not read:
            unread += 1
        item = dict(n)
        item["read"] = read
        items.append(item)

    return {"items": items, "unread": unread}


def mark_read(user_id, keys):
    """标记一批 key 为已读；返回成功标记的条数"""
    if not keys:
        return 0
    return notification_repo.mark_keys_read(user_id, keys)


def current_keys(user_id):
    """当前所有可见通知的 key（用于「全部已读」时一次性标记）"""
    return [n["key"] for n in build(user_id)["items"]]
