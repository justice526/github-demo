"""HTML 统计报告导出模块

生成一份**自包含**的 HTML 报告（内联样式、无外部依赖），
浏览器双击即可打开，也可以用浏览器「打印 → 另存为 PDF」存档。
"""
import os
import sqlite3
from datetime import datetime

from book import get_book_dashboard, get_category_stat, get_hot_book_rank
from rating import get_top_rated, star_text


def get_conn():
    db_path = os.path.join(os.path.dirname(__file__), "library.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _esc(s):
    """转义 HTML 特殊字符，防止书名中的符号破坏页面结构"""
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def collect_stats(user_id=None):
    """收集报告所需的全部统计数据"""
    conn = get_conn()
    cur = conn.cursor()

    def one(sql, args=()):
        cur.execute(sql, args)
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else 0

    data = {
        "user_count": one("SELECT COUNT(*) FROM user"),
        "record_count": one("SELECT COUNT(*) FROM borrow_record"),
        "unreturned": one("SELECT COUNT(*) FROM borrow_record WHERE return_time IS NULL"),
        "overdue": one(
            "SELECT COUNT(*) FROM borrow_record "
            "WHERE return_time IS NULL AND return_deadline < datetime('now','localtime')"),
        "overdue_users": one(
            "SELECT COUNT(DISTINCT user_id) FROM borrow_record "
            "WHERE return_time IS NULL AND return_deadline < datetime('now','localtime')"),
        "penalty_total": round(one("SELECT SUM(penalty) FROM borrow_record"), 2),
    }
    try:
        data["rating_count"] = one("SELECT COUNT(*) FROM rating")
        data["rating_avg"] = round(one("SELECT AVG(score) FROM rating"), 2)
    except sqlite3.OperationalError:
        data["rating_count"] = 0
        data["rating_avg"] = 0.0
    conn.close()

    dash = get_book_dashboard()
    data.update({
        "total_book": dash["total_book"],
        "borrowed": dash["borrowed"],
        "available": dash["available"],
    })
    data["categories"] = get_category_stat()
    data["hot_rank"] = get_hot_book_rank(10)
    data["top_rated"] = get_top_rated(10)

    if user_id is not None:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT username FROM user WHERE id = ?", (user_id,))
        r = cur.fetchone()
        data["me"] = r[0] if r else f"用户#{user_id}"
        cur.execute("SELECT COUNT(*) FROM borrow_record WHERE user_id = ?", (user_id,))
        data["my_total"] = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM borrow_record WHERE user_id = ? AND return_time IS NULL",
            (user_id,))
        data["my_borrowing"] = cur.fetchone()[0]
        conn.close()
    return data


def build_html(user_id=None, operator=None):
    """生成完整 HTML 报告字符串"""
    d = collect_stats(user_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gen_by = operator or d.get("me") or "系统"

    # ---- 概览卡片 ----
    cards = [
        ("图书总数", d["total_book"], "本"),
        ("在架可借", d["available"], "本"),
        ("已借出", d["borrowed"], "本"),
        ("注册用户", d["user_count"], "人"),
        ("借阅记录", d["record_count"], "条"),
        ("逾期未还", d["overdue"], "条"),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="k">{_esc(k)}</div>'
        f'<div class="num">{_esc(v)}<span class="unit">{_esc(u)}</span></div></div>'
        for k, v, u in cards
    )

    # ---- 分类统计（含占比条） ----
    max_total = max([c["total"] for c in d["categories"]], default=1) or 1
    if d["categories"]:
        rows = "".join(
            f'<tr><td>{_esc(c["category"] or "未分类")}</td><td class="c">{c["total"]}</td>'
            f'<td class="c">{c["in_stock"]}</td><td class="c">{c["borrowed"]}</td>'
            f'<td><div class="bar" style="width:{max(4, round(c["total"] * 100 / max_total))}%"></div></td></tr>'
            for c in d["categories"]
        )
    else:
        rows = '<tr><td colspan="5" class="empty">暂无图书数据</td></tr>'
    cat_html = f'''
    <table>
      <thead><tr><th>分类</th><th>总数</th><th>在架</th><th>借出</th><th>占比</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>'''

    # ---- 借阅排行 ----
    if d["hot_rank"]:
        rank_rows = "".join(
            f'<tr><td class="c">{i + 1}</td><td>{_esc(t)}</td><td>{_esc(a)}</td>'
            f'<td class="c">{c}</td></tr>'
            for i, (bid, t, a, c) in enumerate(d["hot_rank"])
        )
    else:
        rank_rows = '<tr><td colspan="4" class="empty">暂无借阅数据</td></tr>'
    rank_html = f'''
    <table>
      <thead><tr><th>名次</th><th>书名</th><th>作者</th><th>借阅次数</th></tr></thead>
      <tbody>{rank_rows}</tbody>
    </table>'''

    # ---- 好评排行 ----
    if d["top_rated"]:
        rate_rows = "".join(
            f'<tr><td class="c">{i + 1}</td><td>{_esc(t)}</td><td>{_esc(a)}</td>'
            f'<td class="star">{star_text(avg)}</td><td class="c">{avg}</td><td class="c">{cnt}</td></tr>'
            for i, (bid, t, a, avg, cnt) in enumerate(d["top_rated"])
        )
    else:
        rate_rows = '<tr><td colspan="6" class="empty">暂无评分数据</td></tr>'
    rate_html = f'''
    <table>
      <thead><tr><th>名次</th><th>书名</th><th>作者</th><th>平均分</th><th>分数</th><th>人数</th></tr></thead>
      <tbody>{rate_rows}</tbody>
    </table>'''

    # ---- 我的借阅摘要 ----
    me_html = ""
    if user_id is not None:
        me_html = f'''
    <section>
      <h2>我的借阅摘要</h2>
      <div class="cards">
        <div class="card"><div class="k">借阅人</div><div class="num sm">{_esc(d.get("me"))}</div></div>
        <div class="card"><div class="k">累计借阅</div><div class="num">{d.get("my_total", 0)}<span class="unit">条</span></div></div>
        <div class="card"><div class="k">当前在借</div><div class="num">{d.get("my_borrowing", 0)}<span class="unit">本</span></div></div>
      </div>
    </section>'''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>图书管理系统 · 统计报告 {now[:10]}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
         background: #eef1f6; color: #2c3e50; margin: 0; padding: 28px 20px; }}
  .wrap {{ max-width: 980px; margin: 0 auto; }}
  header {{ background: #ffffff; border: 1px solid #dfe4ec; border-radius: 12px;
            padding: 22px 26px; margin-bottom: 18px; }}
  h1 {{ margin: 0 0 6px; font-size: 21px; color: #3d6cf5; font-weight: 600; }}
  .meta {{ font-size: 13px; color: #7f8c8d; }}
  section {{ margin-bottom: 22px; }}
  h2 {{ font-size: 15px; font-weight: 600; margin: 0 0 10px; color: #2c3e50;
        padding-left: 9px; border-left: 3px solid #3d6cf5; }}
  .cards {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  .card {{ flex: 1 1 140px; background: #fff; border: 1px solid #dfe4ec;
           border-radius: 10px; padding: 14px 16px; }}
  .k {{ font-size: 12px; color: #7f8c8d; margin-bottom: 6px; }}
  .num {{ font-size: 25px; font-weight: 600; color: #3d6cf5; line-height: 1.15; }}
  .num.sm {{ font-size: 17px; }}
  .unit {{ font-size: 12px; color: #7f8c8d; margin-left: 3px; font-weight: 400; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; overflow: hidden;
           border: 1px solid #dfe4ec; border-radius: 10px; }}
  th, td {{ padding: 9px 13px; text-align: left; font-size: 13px;
            border-bottom: 1px solid #eef1f6; }}
  th {{ background: #e6eaf2; font-weight: 600; color: #2c3e50; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  td.c {{ text-align: center; width: 78px; }}
  td.star {{ color: #e67e22; letter-spacing: 1px; }}
  td.empty {{ text-align: center; color: #7f8c8d; padding: 18px; }}
  .bar {{ height: 12px; background: #3d6cf5; border-radius: 3px; min-width: 4px; }}
  footer {{ text-align: center; font-size: 12px; color: #7f8c8d; padding: 12px 0 4px; }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    header, .card, table {{ border-color: #ccc; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>个人图书管理系统 · 统计报告</h1>
    <div class="meta">生成时间：{now} &nbsp;|&nbsp; 生成人：{_esc(gen_by)}</div>
  </header>

  <section>
    <h2>总体概览</h2>
    <div class="cards">{cards_html}</div>
  </section>
{me_html}
  <section>
    <h2>图书分类统计</h2>
    {cat_html}
  </section>

  <section>
    <h2>借阅次数排行 Top 10</h2>
    {rank_html}
  </section>

  <section>
    <h2>读者好评排行 Top 10</h2>
    {rate_html}
  </section>

  <section>
    <h2>风控提示</h2>
    <div class="cards">
      <div class="card"><div class="k">逾期未还</div><div class="num">{d["overdue"]}<span class="unit">条</span></div></div>
      <div class="card"><div class="k">涉及人数</div><div class="num">{d["overdue_users"]}<span class="unit">人</span></div></div>
      <div class="card"><div class="k">累计罚款</div><div class="num">{d["penalty_total"]}<span class="unit">元</span></div></div>
      <div class="card"><div class="k">评分总数</div><div class="num">{d["rating_count"]}<span class="unit">条</span></div></div>
      <div class="card"><div class="k">平均评分</div><div class="num">{d["rating_avg"]}<span class="unit">分</span></div></div>
    </div>
  </section>

  <footer>本报告由个人图书管理系统自动生成，数据来源于本地 SQLite 数据库。</footer>
</div>
</body>
</html>'''


def export_html_report(save_path="library_report.html", user_id=None, operator=None):
    """把统计报告写为 HTML 文件
    :return: True 成功 / False 失败
    """
    try:
        html = build_html(user_id=user_id, operator=operator)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html)
        return True
    except Exception as e:
        print("导出HTML报告异常：", e)
        return False


if __name__ == "__main__":
    if export_html_report():
        print("报告已生成：library_report.html")
