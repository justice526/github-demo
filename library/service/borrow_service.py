"""借阅业务服务层

承载借阅规则、罚款计算、预约协同等业务编排。

**相对旧实现的关键改进**
旧 borrow.py 借阅时先 commit 图书状态、再 commit 借阅记录，
两步分离；归还时同样分多次提交。中途异常会留下
「书已标记借出但没有借阅记录」这类不一致。
本层把跨表写入收进单个事务，失败自动回滚。
"""

import csv
from datetime import datetime, timedelta

from core import db
from core.errors import ValidationError, NotFoundError, BusinessRuleError
from repository import book_repo, borrow_repo, reservation_repo, rules_repo

# 借阅期限与罚款费率（业务常量，集中在此便于调整）
BORROW_DAYS = 7
PENALTY_PER_DAY = 0.5
# 时间格式，全项目统一
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _now():
    return datetime.now()


def _fmt(dt):
    return dt.strftime(TIME_FMT)


def _parse(s):
    """解析库里的时间字符串，失败抛 BusinessRuleError"""
    try:
        return datetime.strptime(s, TIME_FMT)
    except (ValueError, TypeError) as e:
        raise BusinessRuleError(f"时间格式异常：{s}") from e


# ==================== 借阅规则 ====================

def get_borrow_limit():
    """每人同时可借上限（默认 5）"""
    try:
        return max(1, int(rules_repo.get_value("borrow_limit", rules_repo.DEFAULT_BORROW_LIMIT)))
    except (TypeError, ValueError):
        return rules_repo.DEFAULT_BORROW_LIMIT


def get_fine_threshold():
    """欠费停借阈值（默认 10 元，0 表示不限制）"""
    try:
        return max(0.0, float(rules_repo.get_value(
            "fine_threshold", rules_repo.DEFAULT_FINE_THRESHOLD)))
    except (TypeError, ValueError):
        return float(rules_repo.DEFAULT_FINE_THRESHOLD)


def get_borrow_summary(user_id):
    """汇总某用户借阅状态（取数在 repo，计算在此）"""
    borrowed = rules_repo.count_borrowed(user_id)
    limit = get_borrow_limit()
    return {
        "borrowed": borrowed,
        "overdue": rules_repo.count_overdue(user_id),
        "unpaid_fine": round(float(rules_repo.sum_unpaid_fine(user_id)), 2),
        "limit": limit,
        "remaining": max(0, limit - borrowed),
        "fine_threshold": get_fine_threshold(),
    }


def check_permission(user_id):
    """借阅资格校验

    :return: (allowed, reason) —— reason 为拒绝原因，允许时为空串
    """
    s = get_borrow_summary(user_id)
    if s["overdue"] > 0:
        return False, f"你有 {s['overdue']} 本图书已逾期未还，请先归还后再借阅"
    if s["unpaid_fine"] >= s["fine_threshold"] > 0:
        return False, (f"你累计有 {s['unpaid_fine']} 元罚款未结清"
                       f"（超过 {fmt_num(s['fine_threshold'])} 元阈值），请先缴纳罚款")
    if s["remaining"] <= 0:
        return False, f"你已借满 {s['limit']} 本，请先归还部分图书"
    return True, ""


def fmt_num(v):
    """数字友好显示：10.0 显示为 10，10.5 显示为 10.5"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else str(f)


# ==================== 借阅 / 归还 ====================

def borrow_book(user_id, book_id):
    """借阅图书（含规则校验与预约优先权）

    :return: (ok, msg) —— msg 为可展示给用户的原因
    """
    book = book_repo.find_by_id(book_id)
    if not book:
        return False, "图书不存在"
    _, title, _, _, is_borrow = book
    if is_borrow == 1:
        return False, f"《{title}》已被借出，你可以预约排队"

    allowed, reason = check_permission(user_id)
    if not allowed:
        return False, reason

    # 预约优先权：已有他人排队到书时不能抢借
    holder = reservation_repo.ready_holder(book_id)
    if holder is not None and holder != user_id:
        return False, f"《{title}》已被其他读者预约到书，请等待其取书"

    now = _now()
    deadline = now + timedelta(days=BORROW_DAYS)
    # 改图书状态 + 插借阅记录，两步必须原子生效（SQL 在 repo 层）
    with db.transaction() as cur:
        book_repo.set_borrow_status_in(cur, book_id, True)
        borrow_repo.insert_in(cur, user_id, book_id, _fmt(now), _fmt(deadline))

    # 本人若曾预约这本书，标记为已完成。
    # 注意：不推进队列 —— 书刚被借走仍属借出状态，通知下一位
    # 去取一本借不出的书没有意义。
    from service import reservation_service  # 延迟导入避免循环依赖
    reservation_service.on_book_borrowed(user_id, book_id)

    return True, (f"借阅成功！《{title}》借期 {BORROW_DAYS} 天，"
                  f"请于 {_fmt(deadline)[:16]} 前归还")


def return_book(user_id, book_id):
    """归还图书，超期自动计罚款（每天 0.5 元）

    :return: 罚款金额（float）；无未归还记录时返回 False
    """
    record = borrow_repo.find_active_by_user_book(user_id, book_id)
    if not record:
        return False
    # 按列名取值，不按位置解包 —— 查询列增减时不会静默错位
    rec_id = record["id"]
    deadline_str = record["return_deadline"]

    now = _now()
    penalty = 0.0
    deadline = _parse(deadline_str)
    if now > deadline:
        days = (now - deadline).total_seconds() / (24 * 3600)
        penalty = round(days * PENALTY_PER_DAY, 2)

    # 图书状态与借阅记录一起提交（SQL 在 repo 层）
    with db.transaction() as cur:
        book_repo.set_borrow_status_in(cur, book_id, False)
        borrow_repo.mark_returned_in(cur, rec_id, _fmt(now), penalty)

    # 书真正回到书架，此时才推进预约队列：队首 waiting → ready
    from service import reservation_service  # 延迟导入避免循环依赖
    reservation_service.on_book_returned(book_id)
    return penalty


def renew_book(user_id, book_id, add_days=7):
    """续借：延长应还时间"""
    if add_days <= 0:
        return False, "续借天数必须大于 0"
    record = borrow_repo.find_active_by_user_book(user_id, book_id)
    if not record:
        return False, "没有找到你的未归还借阅记录"
    new_deadline = _parse(record["return_deadline"]) + timedelta(days=add_days)
    borrow_repo.extend_deadline(record["id"], _fmt(new_deadline))
    return True, f"续借成功，新的应还时间：{_fmt(new_deadline)[:16]}"


# ==================== 查询 ====================

def my_records(user_id):
    """我的全部借阅记录（dict 列表，供 GUI 表格直接用）"""
    return [
        {"id": r[0], "title": r[1], "borrow_time": r[2],
         "deadline": r[3], "return_time": r[4], "penalty": r[5]}
        for r in borrow_repo.find_by_user(user_id)
    ]


def my_total_penalty(user_id):
    """我的未结清罚款总额"""
    return round(float(borrow_repo.sum_unpaid_penalty(user_id)), 2)


def my_overdue_books(user_id):
    """我的逾期未还图书（含逾期天数与当前罚款）"""
    now = _now()
    out = []
    for rec_id, title, borrow_time, deadline_str in borrow_repo.find_overdue_raw(user_id):
        try:
            deadline = _parse(deadline_str)
        except BusinessRuleError:
            continue
        if now > deadline:
            days = (now - deadline).total_seconds() / (24 * 3600)
            out.append({
                "record_id": rec_id,
                "title": title,
                "borrow_time": borrow_time,
                "deadline": deadline_str,
                "overdue_days": round(days, 1),
                "current_penalty": round(days * PENALTY_PER_DAY, 2),
            })
    return out


def due_soon_books(user_id, days=3):
    """即将到期提醒（未归还且未逾期）"""
    now = _now()
    out = []
    for rec_id, title, borrow_time, deadline_str in borrow_repo.find_due_soon_raw(user_id):
        try:
            deadline = _parse(deadline_str)
        except BusinessRuleError:
            continue
        if now <= deadline:
            left = (deadline - now).total_seconds() / (24 * 3600)
            if left <= days:
                out.append({
                    "record_id": rec_id, "title": title, "borrow_time": borrow_time,
                    "deadline": deadline_str, "days_left": round(left, 1),
                })
    return out


def book_history(book_id, limit=30):
    """某本书的借阅历史"""
    return borrow_repo.find_history_by_book(book_id, limit)


def my_stats(user_id):
    """我的借阅统计概览"""
    records = borrow_repo.find_by_user(user_id)
    total = len(records)
    active = [r for r in records if not r[4]]
    overdue = [r for r in active
               if r[3] and r[3] < _fmt(_now())]
    return {
        "total": total,
        "active": len(active),
        "returned": total - len(active),
        "overdue": len(overdue),
        "unpaid_fine": round(float(borrow_repo.sum_unpaid_penalty(user_id)), 2),
    }


# ==================== 导出 ====================

def export_my_csv(user_id, save_path="borrow_record.csv"):
    """导出我的借阅记录为 CSV（utf-8-sig 保证 Excel 不乱码）"""
    with open(save_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["记录ID", "书名", "借出时间", "应还时间", "归还时间", "罚款"])
        for r in my_records(user_id):
            w.writerow([r["id"], r["title"], r["borrow_time"],
                        r["deadline"], r["return_time"] or "", r["penalty"]])
    return save_path


def export_all_csv(save_path="all_borrow_records.csv"):
    """导出全部借阅记录为 CSV"""
    with open(save_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["记录ID", "用户", "书名", "借出时间", "应还时间", "归还时间", "罚款"])
        for r in borrow_repo.find_all():
            w.writerow([r[0], r[1] or "", r[2] or "", r[3], r[4], r[5] or "", r[6]])
    return save_path


def export_my_txt(user_id, save_path="borrow_record.txt"):
    """导出我的借阅记录为 txt"""
    lines = ["=" * 46, "我的借阅记录", "=" * 46, ""]
    for r in my_records(user_id):
        state = "已归还" if r["return_time"] else "未归还"
        lines.append(f"《{r['title']}》")
        lines.append(f"  借出：{r['borrow_time']}")
        lines.append(f"  应还：{r['deadline']}")
        lines.append(f"  状态：{state}" + (f"  罚款：{r['penalty']} 元" if r["penalty"] else ""))
        lines.append("")
    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return save_path
