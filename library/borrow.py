import sqlite3
import os
import csv
from datetime import datetime, timedelta

from rules import check_borrow_permission
from reservation import has_priority_holder, on_book_borrowed, on_book_returned
from log import write_log

def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def borrow_book(user_id, book_id):
    """借阅图书
    :param user_id: 用户编号
    :param book_id: 图书编号
    :return: True成功；False失败（图书已借出 / 不满足借阅规则）
    """
    ok, _ = borrow_book_ex(user_id, book_id)
    return ok


def borrow_book_ex(user_id, book_id):
    """借阅图书（带借阅规则校验与预约优先权），返回可展示的原因
    :return: (ok: bool, msg: str)
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT title, is_borrow FROM book WHERE id=?", (book_id,))
    res = cur.fetchone()
    conn.close()
    if not res:
        return False, "图书不存在"
    title, is_borrow = res
    if is_borrow == 1:
        return False, f"《{title}》已被借出，你可以预约排队"

    # 借阅规则校验：逾期未还 / 欠费超限 / 超过借阅上限
    allowed, reason = check_borrow_permission(user_id)
    if not allowed:
        return False, reason

    # 预约优先权：已有其他读者预约到书时，不能抢借
    if has_priority_holder(book_id, user_id):
        return False, f"《{title}》已被其他读者预约到书，请等待其取书"

    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    borrow_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    # 借阅期限7天，算出归还截止时间
    deadline = now + timedelta(days=7)
    deadline_str = deadline.strftime("%Y-%m-%d %H:%M:%S")
    # 修改图书状态为已借出
    cur.execute("UPDATE book SET is_borrow=1 WHERE id=?", (book_id,))
    # 新增借阅记录
    cur.execute('''
        INSERT INTO borrow_record(user_id, book_id, borrow_time, return_deadline, return_time, penalty)
        VALUES (?, ?, ?, ?, NULL, 0)
    ''', (user_id, book_id, borrow_time_str, deadline_str))
    conn.commit()
    conn.close()

    # 若自己有该书的预约，标记为已借到
    on_book_borrowed(user_id, book_id)
    write_log(user_id, "borrow", f"《{title}》#{book_id}", f"应还时间 {deadline_str[:16]}")
    return True, f"借阅成功！《{title}》借期 7 天，请于 {deadline_str[:16]} 前归还"

def return_book(user_id, book_id):
    """归还图书；超时自动计算罚款，每天0.5元
    :param user_id: 当前登录用户ID
    :param book_id: 图书编号
    :return: 成功返回罚款金额，False失败
    """
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    # 取出该用户这条未归还记录的归还截止日期
    cur.execute('''
        SELECT return_deadline FROM borrow_record
        WHERE book_id=? AND user_id=? AND return_time IS NULL
    ''', (book_id, user_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    deadline_str = row[0]
    # 字符串转回datetime对象做时间对比
    deadline = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
    penalty = 0.0
    # 判断是否超时：当前时间 > 截止时间
    if now > deadline:
        # 计算相差多少天
        delta_day = (now - deadline).total_seconds() / (24 * 3600)
        penalty = round(delta_day * 0.5, 2)
    # 更新图书状态为未借出
    cur.execute("UPDATE book SET is_borrow=0 WHERE id=?", (book_id,))
    # 顺带取出书名，便于写操作日志
    cur.execute("SELECT title FROM book WHERE id=?", (book_id,))
    brow = cur.fetchone()
    book_title = brow[0] if brow else ""
    # 更新借阅记录：回填归还时间 + 写入计算出来的罚款penalty
    cur.execute('''
        UPDATE borrow_record
        SET return_time=?, penalty=?
        WHERE book_id=? AND user_id=? AND return_time IS NULL
    ''', (now_str, penalty, book_id, user_id))
    conn.commit()
    conn.close()
    # 归还后推进预约队列：队首 waiting 自动变为 ready（到书通知）
    on_book_returned(book_id)
    write_log(user_id, "return", f"《{book_title}》#{book_id}", f"罚款 {penalty} 元")
    return penalty

def get_borrow_record(user_id):
    """查询某用户全部借阅记录，额外返回罚款penalty字段"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT br.id,b.title,br.borrow_time,br.return_deadline,br.return_time,br.penalty
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ?
    ''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_user_total_penalty(user_id):
    """获取用户全部未结清罚款总和"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT SUM(penalty) FROM borrow_record
        WHERE user_id = ? AND penalty > 0
    ''', (user_id,))
    row = cur.fetchone()
    conn.close()
    total = row[0]
    # SUM无数据返回None，转为0.0防止程序报错
    if total is None:
        return 0.0
    return round(total,2)

def export_borrow_record_to_txt(user_id, save_path="borrow_record.txt"):
    """
    将用户借阅记录导出为txt文本文件
    :param user_id: 用户id
    :param save_path: 输出txt保存路径
    :return: True成功 / False失败
    """
    conn = get_conn()
    cur = conn.cursor()
    sql = """
    SELECT br.book_id, b.title, br.borrow_time, br.return_deadline, br.return_time, br.penalty
    FROM borrow_record br
    LEFT JOIN book b ON br.book_id = b.id
    WHERE br.user_id = ?
    """
    cur.execute(sql,(user_id,))
    records = cur.fetchall()
    conn.close()
    try:
        with open(save_path,"w",encoding="utf-8") as f:
            f.write("====用户借阅记录====\n")
            for row in records:
                bid, title, borrow_t, deadline, return_t, penalty = row
                f.write(f"图书ID:{bid}《{title}》|借阅:{borrow_t} |截止:{deadline} |归还:{return_t} |罚款:{penalty}元\n")
            return True
    except Exception as e:
        print("导出异常：",e)
        return False

# ========== 新增：用户借阅统计概览 ==========
def get_user_borrow_stats(user_id):
    """
    获取用户借阅统计概览
    :return: dict 统计数据
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        # 总借阅数量
        cur.execute("SELECT COUNT(*) FROM borrow_record WHERE user_id = ?", (user_id,))
        total = cur.fetchone()[0]
        # 已归还数量
        cur.execute("SELECT COUNT(*) FROM borrow_record WHERE user_id = ? AND return_time IS NOT NULL", (user_id,))
        returned = cur.fetchone()[0]
        # 未归还数量
        unreturned = total - returned
        # 累计产生罚款总额
        cur.execute("SELECT SUM(penalty) FROM borrow_record WHERE user_id = ?", (user_id,))
        total_penalty = cur.fetchone()[0] or 0.0
        # 逾期未还图书数量
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute('''
            SELECT COUNT(*) FROM borrow_record
            WHERE user_id = ? AND return_time IS NULL AND return_deadline < ?
        ''', (user_id, now_str))
        overdue_cnt = cur.fetchone()[0]
        return {
            "total_borrow": total,
            "returned": returned,
            "unreturned": unreturned,
            "total_penalty": round(total_penalty, 2),
            "overdue_count": overdue_cnt
        }
    except Exception as e:
        print("获取借阅统计异常：", e)
        return {}
    finally:
        conn.close()

# ========== 图书续借 ==========
def renew_book(user_id, book_id, add_days=7):
    """
    图书续借：未归还且未逾期的图书可续借，在原截止时间基础上延长 add_days 天
    :param user_id: 用户ID
    :param book_id: 图书ID
    :param add_days: 续借天数，默认7天
    :return: 成功返回新截止时间字符串，失败返回 False（未找到记录或已逾期）
    """
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    # 查询未归还记录
    cur.execute('''
        SELECT return_deadline FROM borrow_record
        WHERE book_id=? AND user_id=? AND return_time IS NULL
    ''', (book_id, user_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    deadline = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    # 逾期图书不允许续借
    if now > deadline:
        conn.close()
        return False
    # 续借，截止时间 + add_days 天
    new_deadline = deadline + timedelta(days=add_days)
    new_deadline_str = new_deadline.strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("SELECT title FROM book WHERE id=?", (book_id,))
    rrow = cur.fetchone()
    rtitle = rrow[0] if rrow else ""
    cur.execute('''
        UPDATE borrow_record
        SET return_deadline = ?
        WHERE book_id=? AND user_id=? AND return_time IS NULL
    ''', (new_deadline_str, book_id, user_id))
    conn.commit()
    conn.close()
    write_log(user_id, "renew", f"《{rtitle or ''}》#{book_id}",
              f"延长 {add_days} 天，新截止 {new_deadline_str[:16]}")
    return new_deadline_str

# ========== 借阅到期提醒 ==========
def get_due_soon_books(user_id, days=3):
    """
    查询即将到期（days 天内）且未逾期、未归还的图书
    :param user_id: 用户ID
    :param days: 提前提醒天数，默认3天
    :return: list[dict]，含书名、截止时间、剩余天数
    """
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    limit_str = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute('''
        SELECT br.id, b.title, br.return_deadline
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ? AND br.return_time IS NULL
          AND br.return_deadline >= ? AND br.return_deadline <= ?
        ORDER BY br.return_deadline
    ''', (user_id, now_str, limit_str))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        remain = datetime.strptime(r[2], "%Y-%m-%d %H:%M:%S") - now
        result.append({
            "record_id": r[0],
            "title": r[1],
            "deadline": r[2],
            "remain_days": round(remain.total_seconds() / 86400, 1),
        })
    return result


# ========== 借阅记录导出 CSV ==========
def export_borrow_record_to_csv(user_id, save_path="borrow_record.csv"):
    """把用户借阅记录导出为 CSV（带 UTF-8 BOM，Excel 可直接打开不乱码）
    :return: True 成功 / False 失败
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT br.book_id, b.title, b.author, br.borrow_time,
               br.return_deadline, br.return_time, br.penalty
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        WHERE br.user_id = ?
        ORDER BY br.borrow_time DESC
    ''', (user_id,))
    records = cur.fetchall()
    conn.close()
    try:
        with open(save_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["图书ID", "书名", "作者", "借阅时间", "应还时间", "归还时间", "罚款(元)"])
            for row in records:
                writer.writerow([
                    row[0], row[1], row[2], row[3], row[4],
                    row[5] if row[5] else "未归还",
                    row[6] if row[6] else 0
                ])
        return True
    except Exception as e:
        print("导出CSV异常：", e)
        return False


def export_all_borrow_to_csv(save_path="all_borrow_records.csv"):
    """导出全库借阅记录为 CSV（管理员用）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT br.id, u.username, b.title, b.author, br.borrow_time,
               br.return_deadline, br.return_time, br.penalty
        FROM borrow_record br
        LEFT JOIN book b ON br.book_id = b.id
        LEFT JOIN user u ON br.user_id = u.id
        ORDER BY br.borrow_time DESC
    ''')
    records = cur.fetchall()
    conn.close()
    try:
        with open(save_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["记录ID", "借阅人", "书名", "作者", "借阅时间", "应还时间", "归还时间", "罚款(元)"])
            for row in records:
                writer.writerow([
                    row[0], row[1], row[2], row[3], row[4], row[5],
                    row[6] if row[6] else "未归还",
                    row[7] if row[7] else 0
                ])
        return True
    except Exception as e:
        print("导出CSV异常：", e)
        return False


# ========== 某本书的借阅历史 ==========
def get_book_borrow_history(book_id, limit=30):
    """查询某本书的借阅历史（含借阅人用户名）
    :return: [(用户名, 借阅时间, 应还时间, 归还时间, 罚款), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT u.username, br.borrow_time, br.return_deadline, br.return_time, br.penalty
        FROM borrow_record br
        LEFT JOIN user u ON br.user_id = u.id
        WHERE br.book_id = ?
        ORDER BY br.borrow_time DESC
        LIMIT ?
    ''', (book_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_my_current_borrow(user_id, book_id):
    """查询某用户对某本书是否有未归还记录
    :return: (borrow_time, return_deadline) 或 None
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT borrow_time, return_deadline FROM borrow_record
        WHERE user_id = ? AND book_id = ? AND return_time IS NULL
        ORDER BY borrow_time DESC LIMIT 1
    ''', (user_id, book_id))
    row = cur.fetchone()
    conn.close()
    return row


if __name__ == "__main__":
    print("borrow模块加载完成")
