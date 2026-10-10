#!/usr/bin/env python3
"""Web 层端到端冒烟测试（标准库实现，零第三方依赖）。

启动 web 层于本地端口，按公开 API 契约逐项断言；无论成功或失败，
最后都会关闭服务并通过 `git checkout -- library.db` 还原数据库，
确保不污染干净快照（md5 04e5b650963776e44eb4ed311dc8dc1b）。

运行方式：
    python test_web_smoke.py            # 默认端口 8231
    SMOKE_PORT=9001 python test_web_smoke.py
退出码：全部通过为 0，存在失败为 1。
"""
import json
import os
import gc
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from web import ThreadingHTTPServer, ApiHandler  # noqa: E402

PORT = int(os.environ.get("SMOKE_PORT", "8231"))
BASE = "http://127.0.0.1:%d" % PORT
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

_RESULTS = []


def check(name, cond, detail=""):
    _RESULTS.append((name, bool(cond)))
    line = "[%s] %s" % ("PASS" if cond else "FAIL", name)
    if not cond and detail:
        line += " -> " + str(detail)
    print(line)


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), ApiHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(BASE + "/health", timeout=1)
            return server, t
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("web 服务未能在预期时间内启动")


def stop_server(server, t):
    try:
        server.shutdown()
        server.server_close()
    except Exception:
        pass
    t.join(timeout=3)


def restore_db():
    """还原数据库到干净快照（先 gc 释放后台线程持有的 sqlite 连接，再带重试 checkout）"""
    gc.collect()
    time.sleep(0.4)
    for _ in range(10):
        try:
            r = subprocess.run(["git", "checkout", "--", "library.db"],
                               cwd=REPO_DIR, capture_output=True)
            if r.returncode == 0:
                return
        except Exception:
            pass
        time.sleep(0.4)
    print("WARN: git checkout -- library.db 失败，数据库可能已被改动")


def req(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        resp = urllib.request.urlopen(r, timeout=5)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def run_checks():
    # ---- 健康检查 / 首页 ----
    c, d = req("GET", "/health")
    check("health 返回 200", c == 200 and isinstance(d, dict), (c, d))
    html = urllib.request.urlopen(BASE + "/", timeout=5).read().decode()
    check("首页返回内置前端", "图书管理系统" in html and "rank-hot" in html)

    # ---- 认证 ----
    c, d = req("POST", "/api/login", body={"username": "admin", "password": "admin123"})
    check("管理员登录 is_admin=true", c == 200 and d["ok"] and d["data"]["is_admin"] is True, (c, d))
    admin = d["data"]["token"]

    req("POST", "/api/register",
        body={"username": "smoke_user", "password": "pass123",
               "security_q": "?", "security_a": "a"})
    c, d = req("POST", "/api/login", body={"username": "smoke_user", "password": "pass123"})
    check("普通用户登录 is_admin=false", c == 200 and d["ok"] and d["data"]["is_admin"] is False, (c, d))
    user = d["data"]["token"]

    # 第二个全新普通用户（用于制造「借出中」状态；admin 在干净库里有逾期书无法借书）
    req("POST", "/api/register",
        body={"username": "smoke_user2", "password": "pass123",
               "security_q": "?", "security_a": "a"})
    c, d = req("POST", "/api/login", body={"username": "smoke_user2", "password": "pass123"})
    check("第二用户登录 is_admin=false", c == 200 and d["ok"] and d["data"]["is_admin"] is False, (c, d))
    u2 = d["data"]["token"]

    c, d = req("GET", "/api/my/current")
    check("未登录访问受保护接口 401", c == 401, c)

    # ---- 图书列表 / 详情 ----
    c, d = req("GET", "/api/books?page=1&size=20", token=admin)
    books = d["data"]["books"]
    check("列表每项含 avg/count", all(("avg" in b and "count" in b) for b in books), c)
    # 不依赖预置借出数据：取两本首页可借书，自行制造借出状态
    avail_list = [b["id"] for b in books if not b["is_borrow"]]
    check("存在 >=2 本可借书用于测试", len(avail_list) >= 2, len(avail_list))
    avail = avail_list[0]    # 全程保持可借（供借还/续借/评分/高分榜）
    avail2 = avail_list[1]   # 由管理员借走制造「借出中」状态

    c, d = req("GET", "/api/books/%d" % avail, token=admin)
    check("图书详情含 rating 与 tags", c == 200 and "rating" in d["data"]
          and isinstance(d["data"].get("tags"), list), c)

    # ---- 管理员增改删 ----
    c, d = req("POST", "/api/books", token=admin,
               body={"title": "冒烟书A", "author": "u", "category": "c"})
    check("新增图书 201", c == 201 and d["ok"], (c, d))
    nid = d["data"]["id"]
    c, d = req("PUT", "/api/books/%d" % nid, token=admin,
               body={"title": "冒烟书A2", "author": "u", "category": "c"})
    check("修改图书 200", c == 200 and d["ok"], (c, d))
    c, d = req("DELETE", "/api/books/%d" % nid, token=admin)
    check("删除图书 200", c == 200 and d["ok"], (c, d))
    c, d = req("GET", "/api/books/%d" % nid, token=admin)
    check("删除后查询 404", c == 404, c)

    # ---- 借阅 / 归还 / 续借（用 avail，全程保持可借）----
    c, d = req("POST", "/api/borrow", token=user, body={"book_id": avail})
    check("借阅 200", c == 200 and d["ok"], (c, d))
    c, d = req("GET", "/api/my/current", token=user)
    check("我的当前借阅含该书", any(it["book_id"] == avail for it in d["data"]["items"]), c)
    c, d = req("POST", "/api/return", token=user, body={"book_id": avail})
    check("归还 200", c == 200 and d["ok"], (c, d))
    c, d = req("GET", "/api/my/current", token=user)
    check("归还后不在当前列表", not any(it["book_id"] == avail for it in d["data"]["items"]), c)

    # 第二用户借走 avail2，自行制造「借出中」状态（不再依赖预置数据；admin 有逾期书无法借）
    c, d = req("POST", "/api/borrow", token=u2, body={"book_id": avail2})
    check("第二用户借走 avail2 制造借出中状态", c == 200 and d["ok"], (c, d))
    borrowed = avail2

    c, d = req("POST", "/api/borrow", token=user, body={"book_id": borrowed})
    check("借阅借出中的书 422", c == 422, (c, d))

    c, d = req("POST", "/api/borrow", token=user, body={"book_id": avail})
    check("再次借阅 avail 200", c == 200 and d["ok"], (c, d))
    c, d = req("POST", "/api/renew", token=user, body={"book_id": avail, "days": 7})
    check("续借 200", c == 200 and d["ok"], (c, d))
    req("POST", "/api/return", token=user, body={"book_id": avail})

    # ---- 预约 / 取消 ----
    c, d = req("POST", "/api/reserve", token=user, body={"book_id": borrowed})
    check("预约借出中的书 200", c == 200 and d["ok"], (c, d))
    c, d = req("POST", "/api/reserve", token=user, body={"book_id": borrowed})
    check("重复预约 422", c == 422, (c, d))
    c, d = req("GET", "/api/my/reservations", token=user)
    check("我的预约含该书(排队中)",
          any(it["book_id"] == borrowed and it["status"] == "排队中" for it in d["data"]["items"]), c)
    c, d = req("GET", "/api/books/%d/reservations" % borrowed, token=user)
    check("预约队列人数 >= 1", d["data"]["count"] >= 1, c)
    c, d = req("POST", "/api/reserve", token=user, body={"book_id": avail})
    check("预约在架书 422", c == 422, (c, d))
    c, d = req("POST", "/api/reserve/cancel", token=user, body={"book_id": borrowed})
    check("取消预约 200", c == 200 and d["ok"], (c, d))
    c, d = req("GET", "/api/my/reservations?history=1", token=user)
    check("历史含已取消预约",
          any(it["book_id"] == borrowed and it["status"] == "已取消" for it in d["data"]["items"]), c)

    # ---- 评分 ----
    c, d = req("POST", "/api/books/%d/rating" % avail, token=user,
               body={"score": 5, "comment": "好书"})
    check("提交评分 200", c == 200 and d["ok"], (c, d))
    c, d = req("GET", "/api/books/%d/rating" % avail, token=user)
    check("我的评分=5", d["data"]["my_score"] == 5, c)
    c, d = req("GET", "/api/books/%d/rating" % avail, token=admin)
    check("评分接口返回 my_score(管理员)", "my_score" in d["data"], c)
    c, d = req("POST", "/api/books/%d/rating" % avail, token=user, body={"score": 9})
    check("越界评分 400", c == 400, (c, d))
    c, d = req("POST", "/api/books/%d/rating" % avail, token=user, body={"score": "x"})
    check("非整数评分 400", c == 400, (c, d))
    c, d = req("GET", "/api/books/top-rated?top=100", token=admin)
    check("高分榜含该书", any(x["book_id"] == avail for x in d["data"]["items"]), c)

    # ---- 统计 / 排行 ----
    c, d = req("GET", "/api/stats/dashboard", token=admin)
    check("仪表盘含 total_book", c == 200 and "total_book" in d["data"], c)
    c, d = req("GET", "/api/books/rank?top=5", token=admin)
    check("借阅排行返回列表", c == 200 and isinstance(d["data"]["rank"], list), c)

    # ---- 错误码与权限 ----
    c, d = req("POST", "/api/books", token=user,
               body={"title": "x", "author": "y", "category": "z"})
    check("普通用户新增图书 403", c == 403, (c, d))
    c, d = req("GET", "/api/books/999999", token=admin)
    check("不存在图书 404", c == 404, c)
    c, d = req("GET", "/api/my/records", token=user)
    check("我的记录 200", c == 200 and d["ok"], c)
    c, d = req("GET", "/api/my/summary", token=user)
    check("我的摘要 200", c == 200 and d["ok"], c)


def main():
    server, t = start_server()
    try:
        run_checks()
    finally:
        stop_server(server, t)
        restore_db()
    passed = sum(1 for r in _RESULTS if r[1])
    failed = [r for r in _RESULTS if not r[1]]
    print("\n==== 冒烟测试结果：%d 通过 / %d 失败 ====" % (passed, len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
