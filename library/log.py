"""操作日志模块（审计）

记录系统中的关键动作，便于追溯「谁在什么时候做了什么」。
设计原则：**写日志失败绝不能影响主业务**，所有异常都吞掉并打印。
"""
import sqlite3
import os
from datetime import datetime


def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# 动作代码 → 中文名
ACTION_TEXT = {
    "register": "注册",
    "login": "登录",
    "logout": "注销",
    "borrow": "借阅",
    "return": "归还",
    "renew": "续借",
    "rate": "评分",
    "reserve": "预约",
    "cancel_reserve": "取消预约",
    "recharge": "充值",
    "pay_fine": "缴纳罚款",
    "add_book": "新增图书",
    "delete_book": "删除图书",
    "update_book": "修改图书",
    "export": "导出数据",
}


def action_text(code):
    return ACTION_TEXT.get(code, code)


def init_log_table():
    """创建操作日志表（幂等）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS operation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            target TEXT,
            detail TEXT,
            log_time TEXT
        )
    ''')
    conn.commit()
    conn.close()
    return True


def write_log(user_id, action, target="", detail=""):
    """写一条操作日志
    :param user_id: 操作人ID，未登录可传 None
    :param action: 动作代码，见 ACTION_TEXT
    :param target: 操作对象描述，如「《三体》#7」
    :param detail: 补充说明
    :return: True/False（本函数不会抛异常）
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        username = None
        if user_id is not None:
            cur.execute("SELECT username FROM user WHERE id = ?", (user_id,))
            row = cur.fetchone()
            username = row[0] if row else None
        cur.execute('''
            INSERT INTO operation_log(user_id, username, action, target, detail, log_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, action, str(target or ""), str(detail or ""),
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        # 写日志是「附加价值」，失败不能影响主流程
        print("写操作日志异常：", e)
        return False


def get_logs(limit=100, action=None, user_id=None):
    """查询操作日志（倒序）
    :return: [(ID, 用户名, 动作, 对象, 详情, 时间), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    sql = "SELECT id, username, action, target, detail, log_time FROM operation_log WHERE 1=1"
    params = []
    if action:
        sql += " AND action = ?"
        params.append(action)
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return rows


def get_action_stats():
    """各动作计数（用于概览展示）
    :return: [(动作代码, 中文名, 次数), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT action, COUNT(*) c FROM operation_log
            GROUP BY action ORDER BY c DESC
        ''')
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    return [(r[0], action_text(r[0]), r[1]) for r in rows]


def get_log_count():
    conn = get_conn()
    cur = conn.cursor()
    try:
        n = cur.execute("SELECT COUNT(*) FROM operation_log").fetchone()[0]
    except sqlite3.OperationalError:
        n = 0
    finally:
        conn.close()
    return n


def clear_logs():
    """清空操作日志（管理员用），返回清空条数"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM operation_log")
        conn.commit()
        return cur.rowcount
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    init_log_table()
    print("log 模块加载完成，当前日志条数：", get_log_count())
