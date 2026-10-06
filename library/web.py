"""REST API 层 —— 复用四层架构中的 service 层

纯标准库实现（http.server + json），零第三方依赖。

设计要点
--------
1. **控制器只做三件事**：解析请求 → 调 service → 格式化响应。
   业务逻辑全部在 service 层，这里不写任何业务判断。
2. **统一错误处理**：service 抛出的类型化异常（AppError）由
   `core.errors.http_status_of` 映射成 HTTP 状态码，客户端永远
   拿到 `{ok, code, message}` 的规范结构，看不到堆栈。
3. **简单 token 认证**：登录返回一个内存态 token，后续请求带
   `Authorization: Bearer <token>`。这是单机演示的最小实现，
   生产环境应换 JWT + 服务端刷新令牌（见 README 注意事项）。
4. **线程安全**：SQLite 连接按线程隔离（core.db 已保证），
   用 ThreadingHTTPServer 处理并发请求。

启动方式::

    python web.py            # 默认 127.0.0.1:8000
    python web.py 9000       # 指定端口

接口一览（响应均为 JSON）::

    GET    /health                 健康检查
    POST   /api/login              登录，返回 token
    POST   /api/register           注册
    GET    /api/books              图书列表（?page=&size=&q=&category=）
    GET    /api/books/<id>         图书详情
    POST   /api/books              新增图书（管理员）
    PUT    /api/books/<id>         修改图书
    DELETE /api/books/<id>         删除图书
    POST   /api/borrow             借阅 {book_id}
    POST   /api/return             归还 {book_id}
    POST   /api/renew              续借 {book_id, days}
    GET    /api/my/records         我的借阅记录
    GET    /api/my/summary         我的借阅摘要
    GET    /api/stats/dashboard    统计仪表盘
    GET    /api/books/rank         热门借阅排行
    GET    /api/books/<id>/rating  图书评分
    POST   /api/books/<id>/rating  评分 {score, comment}
    POST   /api/reserve             预约图书 {book_id}
    POST   /api/reserve/cancel      取消预约 {book_id}
    GET    /api/my/reservations     我的预约（?history=1 含历史）
    GET    /api/books/<id>/reservations  某书预约队列与人数
"""

import json
import os
import re
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from core.errors import (AppError, AuthError, PermissionError_, NotFoundError,
                         ValidationError, BusinessRuleError)
from core.errors import http_status_of
from core.db import get_conn, close_connection
from repository import book_repo, borrow_repo
from service import (book_service, user_service, borrow_service,
                     rating_service, reservation_service, tag_service)

# ===== 内存 token 表（单机演示用）=====
# token -> user_id。生产环境应改为 JWT（短时效访问令牌 + 服务端刷新令牌）。
_TOKENS = {}
_TOKEN_LOCK = __import__("threading").Lock()


def _issue_token(user_id):
    token = secrets.token_urlsafe(24)
    with _TOKEN_LOCK:
        _TOKENS[token] = user_id
    return token


def _resolve_token(handler):
    """从请求头解析 token，返回 user_id；无 token 返回 None"""
    auth = handler.headers.get("Authorization", "")
    m = re.match(r"^Bearer\s+(\S+)$", auth)
    if not m:
        return None
    with _TOKEN_LOCK:
        return _TOKENS.get(m.group(1))


def _require_user(handler):
    """要求登录：未登录抛 AuthError"""
    uid = _resolve_token(handler)
    if uid is None:
        raise AuthError("请先登录")
    return uid


def _require_admin(handler):
    """要求管理员：非管理员抛 PermissionError_"""
    uid = _require_user(handler)
    if not user_service.is_admin(uid):
        raise PermissionError_("该操作仅管理员可执行")
    return uid


def _read_json(handler):
    """读取并解析 JSON 请求体；空 body 返回 {}"""
    try:
        length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        raise ValidationError("请求体长度非法")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("请求体不是合法 JSON")
    if not isinstance(data, dict):
        raise ValidationError("请求体应为 JSON 对象")
    return data


def _json_response(handler, status, payload):
    """输出 JSON 响应"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def _ok(handler, data=None, status=200):
    _json_response(handler, status, {"ok": True, "data": data})


def _fail(handler, exc):
    status = http_status_of(exc)
    payload = {"ok": False, "code": getattr(exc, "code", "error"),
               "message": str(exc.message) if isinstance(exc, AppError) else str(exc)}
    _json_response(handler, status, payload)


class ApiHandler(BaseHTTPRequestHandler):
    """请求处理器：路由 + 异常兜底"""

    # 路由表： (方法, 正则) -> 处理函数
    ROUTES = []

    def _dispatch(self, method, path):
        for (m, pattern, func) in self.ROUTES:
            if m != method:
                continue
            match = pattern.match(path)
            if match:
                return func(self, **match.groupdict())
        return None

    def _route(self, method):
        """主分发：统一 try/except，异常转 JSON"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            # 先处理 CORS 预检
            if method == "OPTIONS":
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods",
                                 "GET, POST, PUT, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers",
                                 "Content-Type, Authorization")
                self.end_headers()
                return
            result = self._dispatch(method, path)
            if result is None:
                raise NotFoundError(f"接口不存在：{method} {path}")
        except AppError as e:
            _fail(self, e)
        except Exception as e:  # 兜底，绝不把堆栈发给客户端
            _fail(self, AppError(f"服务器内部错误", code="internal_error", detail=str(e)))

    def do_GET(self):
        # 首页与静态资源：直接返回前端，其余走 API 路由
        if self.path in ("/", "/index.html"):
            self._serve_homepage()
            return
        self._route("GET")

    def _serve_homepage(self):
        """返回自包含的单页前端（static/index.html）"""
        base = os.path.dirname(os.path.abspath(__file__))
        index_path = os.path.join(base, "static", "index.html")
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                body = f.read().encode("utf-8")
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")

    def do_OPTIONS(self):
        self._route("OPTIONS")

    def log_message(self, *args):
        """静默默认日志，避免刷屏（需要时打开）"""
        pass


# ==================== 路由注册 ====================

def _register(method, path_regex):
    """装饰器：把处理函数挂到 ApiHandler.ROUTES"""
    pattern = re.compile("^" + path_regex + "$")
    def deco(func):
        ApiHandler.ROUTES.append((method, pattern, func))
        return func
    return deco


# ---- 健康检查 / 认证 ----

@_register("GET", r"/health")
def health(handler):
    return _ok(handler, {"status": "up", "books": book_repo.count_all()})


@_register("POST", r"/api/login")
def login(handler):
    data = _read_json(handler)
    uid = user_service.login(data.get("username", ""), data.get("password", ""))
    return _ok(handler, {"token": _issue_token(uid),
                         "user_id": uid,
                         "username": data.get("username"),
                         "is_admin": bool(user_service.is_admin(uid))})


@_register("POST", r"/api/register")
def register(handler):
    data = _read_json(handler)
    uid = user_service.register(data.get("username", ""), data.get("password", ""),
                                data.get("security_q", ""), data.get("security_a", ""))
    return _ok(handler, {"user_id": uid}, status=201)


# ---- 图书 ----

@_register("GET", r"/api/books")
def list_books(handler):
    qs = parse_qs(urlparse(handler.path).query)
    q = (qs.get("q") or [""])[0]
    category = (qs.get("category") or [""])[0]
    page = int((qs.get("page") or ["1"])[0])
    size = int((qs.get("size") or ["20"])[0])
    if q:
        books = book_service.search(q)
    elif category:
        books = book_service.list_by_category(category)
    else:
        books = book_service.page(page, size)[0]
    return _ok(handler, {"books": [_book_dict(b) for b in books]})


@_register("GET", r"/api/books/rank")
def rank_books(handler):
    qs = parse_qs(urlparse(handler.path).query)
    top_n = int((qs.get("top") or ["10"])[0])
    return _ok(handler, {"rank": book_service.hot_rank(top_n)})


@_register("GET", r"/api/books/(?P<bid>\d+)")
def get_book(handler, bid):
    book = book_service.get_detail(int(bid))
    d = _book_dict(book)
    d["rating"] = rating_service.get_rating(int(bid))
    d["tags"] = tag_service.book_tags(int(bid))
    return _ok(handler, d)


@_register("POST", r"/api/books")
def add_book(handler):
    _require_admin(handler)
    data = _read_json(handler)
    bid = book_service.add_book(data.get("title", ""), data.get("author", ""),
                                data.get("category", ""))
    return _ok(handler, {"id": bid}, status=201)


@_register("PUT", r"/api/books/(?P<bid>\d+)")
def update_book(handler, bid):
    _require_admin(handler)
    data = _read_json(handler)
    book_service.update_book(int(bid), data.get("title", ""),
                             data.get("author", ""), data.get("category"))
    return _ok(handler, {"updated": True})


@_register("DELETE", r"/api/books/(?P<bid>\d+)")
def delete_book(handler, bid):
    _require_admin(handler)
    book_service.delete_book(int(bid))
    return _ok(handler, {"deleted": True})


# ---- 借阅 ----

@_register("POST", r"/api/borrow")
def borrow(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    ok, msg = borrow_service.borrow_book(uid, int(data.get("book_id", 0)))
    if not ok:
        # 借阅被拒是业务规则冲突（如已借出/超限/逾期），不是服务器错误
        raise BusinessRuleError(msg)
    return _ok(handler, {"message": msg})


@_register("POST", r"/api/return")
def return_book(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    penalty = borrow_service.return_book(uid, int(data.get("book_id", 0)))
    if penalty is False:
        raise NotFoundError("没有找到未归还的借阅记录")
    return _ok(handler, {"penalty": penalty})


@_register("POST", r"/api/renew")
def renew(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    ok, msg = borrow_service.renew_book(uid, int(data.get("book_id", 0)),
                                        int(data.get("days", 7)))
    if not ok:
        raise BusinessRuleError(msg)
    return _ok(handler, {"message": msg})


@_register("GET", r"/api/my/records")
def my_records(handler):
    uid = _require_user(handler)
    return _ok(handler, {"records": borrow_service.my_records(uid)})


@_register("GET", r"/api/my/current")
def my_current(handler):
    """我当前未归还的借阅（含 book_id，供前端归还操作）"""
    uid = _require_user(handler)
    rows = borrow_repo.find_active_by_user(uid)
    return _ok(handler, {"items": [
        {"record_id": r[0], "book_id": r[1], "title": r[2],
         "borrow_time": r[3], "deadline": r[4]} for r in rows
    ]})


@_register("GET", r"/api/my/summary")
def my_summary(handler):
    uid = _require_user(handler)
    return _ok(handler, borrow_service.get_borrow_summary(uid))


# ---- 评分 ----

@_register("GET", r"/api/books/(?P<bid>\d+)/rating")
def get_rating(handler, bid):
    return _ok(handler, rating_service.get_rating(int(bid)))


@_register("POST", r"/api/books/(?P<bid>\d+)/rating")
def rate(handler, bid):
    uid = _require_user(handler)
    data = _read_json(handler)
    rating_service.rate(uid, int(bid), data.get("score"), data.get("comment", ""))
    return _ok(handler, {"rated": True})


# ---- 预约 ----

@_register("POST", r"/api/reserve")
def reserve_book(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    ok, msg = reservation_service.reserve(uid, int(data.get("book_id", 0)))
    if not ok:
        raise BusinessRuleError(msg)
    return _ok(handler, {"message": msg})


@_register("POST", r"/api/reserve/cancel")
def cancel_reserve(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    ok, msg = reservation_service.cancel(uid, int(data.get("book_id", 0)))
    if not ok:
        raise BusinessRuleError(msg)
    return _ok(handler, {"message": msg})


@_register("GET", r"/api/my/reservations")
def my_reservations(handler):
    uid = _require_user(handler)
    qs = parse_qs(urlparse(handler.path).query)
    history = (qs.get("history") or ["0"])[0] in ("1", "true", "yes")
    return _ok(handler, {"items": reservation_service.my_reservations(uid, include_history=history)})


@_register("GET", r"/api/books/(?P<bid>\d+)/reservations")
def book_queue(handler, bid):
    _require_user(handler)
    return _ok(handler, {"queue": reservation_service.queue_of(int(bid)),
                         "count": reservation_service.reservation_count(int(bid))})


# ---- 统计 ----

@_register("GET", r"/api/stats/dashboard")
def dashboard(handler):
    return _ok(handler, book_service.dashboard())


def _book_dict(book):
    """把 (id, title, author, category, is_borrow) 元组转成 JSON 友好的 dict"""
    return {
        "id": book[0], "title": book[1], "author": book[2],
        "category": book[3], "is_borrow": bool(book[4]),
    }


def run(host="127.0.0.1", port=8000):
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"图书管理系统 REST API 已启动：http://{host}:{port}")
    print("健康检查：curl http://%s:%s/health" % (host, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()
        close_connection()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run(port=port)
