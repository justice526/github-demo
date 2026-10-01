"""借阅规则与权限校验模块

负责三件事：
1. 维护可配置的系统参数（借阅上限、欠费暂停阈值），存于 config 表
2. 汇总用户的借阅状态（在借数量、逾期、欠费、剩余额度）
3. 给出「能否借书」的判定与拒绝原因

config 表与 reservation 表一样由本模块幂等创建，不改动 db.py。
"""
import sqlite3
import os

DEFAULT_BORROW_LIMIT = 5        # 每人同时最多可借阅册数
DEFAULT_FINE_THRESHOLD = 10.0   # 未结清罚款达到该金额则暂停借阅权限


def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_rules_table():
    """创建 config 参数表（幂等）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()
    return True


# ========== 参数读写 ==========
def get_config(key, default=None):
    """读取一个配置项，不存在时返回 default"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default
    except sqlite3.OperationalError:
        return default
    finally:
        conn.close()


def set_config(key, value):
    """写入一个配置项（存在则覆盖）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO config(key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    ''', (key, str(value)))
    conn.commit()
    conn.close()
    return True


def get_borrow_limit():
    """每人同时可借阅的册数上限"""
    try:
        return max(1, int(get_config("borrow_limit", DEFAULT_BORROW_LIMIT)))
    except (TypeError, ValueError):
        return DEFAULT_BORROW_LIMIT


def set_borrow_limit(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return False
    if n < 1:
        return False
    set_config("borrow_limit", n)
    return True


def get_fine_threshold():
    """欠费达到该金额即暂停借阅"""
    try:
        return max(0.0, float(get_config("fine_threshold", DEFAULT_FINE_THRESHOLD)))
    except (TypeError, ValueError):
        return DEFAULT_FINE_THRESHOLD


def set_fine_threshold(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return False
    if v < 0:
        return False
    set_config("fine_threshold", v)
    return True


# ========== 用户借阅状态 ==========
def get_borrow_summary(user_id):
    """汇总某用户的借阅状态
    :return: dict，含在借数、逾期数、欠费、额度与剩余可借数
    """
    conn = get_conn()
    cur = conn.cursor()
    # 未归还数量
    cur.execute("SELECT COUNT(*) FROM borrow_record WHERE user_id = ? AND return_time IS NULL", (user_id,))
    borrowed = cur.fetchone()[0] or 0
    # 逾期未还数量
    cur.execute('''
        SELECT COUNT(*) FROM borrow_record
        WHERE user_id = ? AND return_time IS NULL
          AND return_deadline < datetime('now', 'localtime')
    ''', (user_id,))
    overdue = cur.fetchone()[0] or 0
    # 未结清罚款
    cur.execute("SELECT SUM(penalty) FROM borrow_record WHERE user_id = ? AND penalty > 0", (user_id,))
    unpaid = cur.fetchone()[0] or 0.0
    conn.close()

    limit = get_borrow_limit()
    threshold = get_fine_threshold()
    remaining = max(0, limit - borrowed)
    return {
        "borrowed": borrowed,
        "overdue": overdue,
        "unpaid_fine": round(float(unpaid), 2),
        "limit": limit,
        "remaining": remaining,
        "fine_threshold": threshold,
    }


def check_borrow_permission(user_id):
    """校验用户是否具备借阅资格
    :return: (allowed: bool, reason: str)  reason 为拒绝原因，允许时为空串
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
    """把 10.0 这类数字显示为 10，2.5 保持 2.5"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else str(f)


def get_borrow_rule_text():
    """把当前规则拼成一句可展示的说明"""
    limit = get_borrow_limit()
    threshold = get_fine_threshold()
    return (f"借阅规则：每人同时最多借 {limit} 本；"
            f"有逾期未还图书时暂停借阅；未结清罚款达 {fmt_num(threshold)} 元时暂停借阅；"
            f"借期 7 天，逾期每天 0.5 元。")


def get_rule_config():
    """返回全部规则参数（供设置界面回填）"""
    return {
        "borrow_limit": get_borrow_limit(),
        "fine_threshold": get_fine_threshold(),
    }


if __name__ == "__main__":
    init_rules_table()
    print("rules 模块加载完成")
    print(get_borrow_rule_text())
