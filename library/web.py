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

    GET    /health                 健康检查（存活探针）
    GET    /ready                  就绪探针（检查数据库可达，不可达返回 503）
    POST   /api/login              登录，返回 token + refresh_token
    POST   /api/refresh            用 refresh_token 换新令牌（轮换吊销旧令牌）
    POST   /api/logout             吊销 refresh_token
    POST   /api/register           注册
    POST   /api/me/password        修改自己的密码 {old_password, new_password}
    GET    /api/security-question  取密保问题 ?username=（找回密码前置）
    POST   /api/reset-password     通过密保重置密码 {username, answer, new_password}
    GET    /api/me/penalty         我的未结清罚款
    GET    /api/users              用户列表（管理员）
    POST   /api/users/<id>/recharge 给用户充值 {amount}（管理员）
    GET    /api/admin/borrows      全部借阅记录（管理员）
    GET    /api/admin/overdue      逾期未还报表（管理员）
    GET    /api/admin/logs         操作审计日志（管理员，?limit=&action=&user_id=，含统计）
    GET    /api/admin/logs/export  导出操作审计日志 CSV（管理员，?limit=&action=&user_id=）
    GET    /api/my/due-soon        即将到期提醒（?days=，默认 3 天）
    GET    /api/my/stats           我的借阅统计
    GET    /api/books/<id>/history 某书借阅历史
    GET    /api/export/my-borrows  导出我的借阅记录 CSV
    GET    /api/export/all-borrows 导出全部借阅记录 CSV（管理员）
    GET    /api/me/balance         我的余额
    POST   /api/me/pay-fine        缴纳我的全部未结清罚款（从余额扣）
    GET    /api/rules              查看借阅规则（借阅上限/欠费阈值）
    POST   /api/rules              设置借阅规则（管理员）
    GET    /api/books              图书列表（?page=&size=&q=&category=&tag=a&tag=b&match=any|all）
    GET    /api/books/<id>         图书详情
    POST   /api/books              新增图书（管理员）
    PUT    /api/books/<id>         修改图书
    DELETE /api/books/<id>         删除图书
    GET    /api/tags               全部标签及每标签书数
    POST   /api/books/<id>/tags    设置某书标签（管理员，覆盖式 {tags}）
    POST   /api/borrow             借阅 {book_id}
    POST   /api/return             归还 {book_id}
    POST   /api/renew              续借 {book_id, days}
    GET    /api/my/records         我的借阅记录
    GET    /api/my/summary         我的借阅摘要
    GET    /api/stats/dashboard    统计仪表盘
    GET    /api/books/rank         热门借阅排行
    GET    /api/books/top-rated    高分榜（按均分，?top=）
    GET    /api/books/<id>/rating  图书评分
    POST   /api/books/<id>/rating  评分 {score, comment}
    POST   /api/reserve             预约图书 {book_id}
    POST   /api/reserve/cancel      取消预约 {book_id}
    GET    /api/my/reservations     我的预约（?history=1 含历史）
    GET    /api/books/<id>/reservations  某书预约队列与人数
    GET    /api/notifications        我的通知中心（聚合待取/即将到期/逾期，含未读数）
    POST   /api/notifications/read   标记通知已读 {keys:[...]} 或 {all:true}
"""

import json
import logging
import os
import re
import signal
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from core import jwt
from core.errors import (AppError, AuthError, PermissionError_, NotFoundError,
                         ValidationError, BusinessRuleError, RateLimitError,
                         PayloadTooLargeError)
from core.errors import http_status_of
from core.db import get_conn, close_connection, query_one

# 结构化访问日志（12-factor：JSON 行输出到 stderr，便于采集；不污染业务 stdout）
_access_logger = logging.getLogger("library.access")
if not _access_logger.handlers:
    _access_handler = logging.StreamHandler(sys.stderr)
    _access_handler.setFormatter(logging.Formatter("%(message)s"))
    _access_logger.addHandler(_access_handler)
    _access_logger.setLevel(logging.INFO)
    _access_logger.propagate = False
from repository import (book_repo, borrow_repo, tag_repo, refresh_token_repo,
                       notification_repo, log_repo)
from service import (book_service, user_service, borrow_service,
                     rating_service, reservation_service, tag_service,
                     rules_service, notification_service, log_service)

# 标签与刷新令牌表：导入时幂等建表，保证任何启动路径表都存在。
tag_repo.init_table()
refresh_token_repo.init_table()
notification_repo.init_table()
log_repo.init_table()
close_connection()  # 释放导入线程（主线程）持有的连接，避免退出/测试时文件锁

# ===== 生产加固配置（集中来自环境变量 / .env，详见 core/config.py）=====
from core.config import (JWT_SECRET, ACCESS_TTL, REFRESH_TTL, RATE_LIMIT,
                         RATE_WINDOW, CORS_ORIGINS as _CORS_ORIGINS)

# 限流计数（按客户端 IP 的固定窗口），进程内存态，演示够用
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS = {}  # ip -> [窗口起点, 计数]


def _issue_tokens(uid):
    """签发 (访问令牌 JWT, 刷新令牌)；刷新令牌服务端存储，可吊销/轮换"""
    access = jwt.encode({"sub": str(uid)}, JWT_SECRET, ttl=ACCESS_TTL)
    refresh = refresh_token_repo.create(uid, REFRESH_TTL)
    return access, refresh


def _resolve_token(handler):
    """从 Bearer 头解出 user_id；失效/非法返回 None"""
    auth = handler.headers.get("Authorization", "")
    m = re.match(r"^Bearer\s+(\S+)$", auth)
    if not m:
        return None
    try:
        payload = jwt.decode(m.group(1), JWT_SECRET)
        return int(payload.get("sub"))
    except (ValueError, TypeError):
        return None


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


def _audit(action, uid, target="", detail=""):
    """写操作审计日志（最佳努力，失败绝不抛异常、不影响主流程）"""
    try:
        log_service.write(uid, action, target, detail)
    except Exception:
        pass


def _rate_allowed(handler):
    """固定窗口限流：未超限返回 True。兜底放行，避免配置异常阻断服务。"""
    client = handler.client_address[0]
    now = time.time()
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS.get(client)
        if bucket is None or now - bucket[0] >= RATE_WINDOW:
            _RATE_BUCKETS[client] = [now, 1]
            return True
        bucket[1] += 1
        return bucket[1] <= RATE_LIMIT


# JSON API 请求体上限：1 MiB。超大体请求直接拒绝，防止恶意 Content-Length 撑爆内存（DoS）。
MAX_BODY_BYTES = 1 << 20


def _read_json(handler):
    """读取并解析 JSON 请求体；空 body 返回 {}"""
    try:
        length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        raise ValidationError("请求体长度非法")
    if length <= 0:
        return {}
    if length > MAX_BODY_BYTES:
        raise PayloadTooLargeError("请求体过大（上限 %d 字节）" % MAX_BODY_BYTES)
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


# 统一附加的安全响应头
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy":
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'",
}


def _cors_origin(handler):
    """按白名单返回允许的 Origin；未配置则返回 None（仅同源）"""
    if not _CORS_ORIGINS:
        return None
    origin = handler.headers.get("Origin")
    return origin if origin in _CORS_ORIGINS else _CORS_ORIGINS[0]


def _emit_common_headers(handler):
    """附加 CORS（若配置）与安全头，供所有响应复用"""
    origin = _cors_origin(handler)
    if origin:
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Access-Control-Allow-Credentials", "true")
        handler.send_header("Vary", "Origin")
    for k, v in _SECURITY_HEADERS.items():
        handler.send_header(k, v)


def _json_response(handler, status, payload):
    """输出 JSON 响应"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _emit_common_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)


def _ok(handler, data=None, status=200):
    _json_response(handler, status, {"ok": True, "data": data})


def _csv_response(handler, filename, content):
    """输出 CSV 文件下载响应（utf-8-sig，Excel 不乱码）"""
    body = content.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/csv; charset=utf-8")
    handler.send_header(
        "Content-Disposition",
        "attachment; filename=\"%s\"" % filename.replace("\"", ""))
    handler.send_header("Content-Length", str(len(body)))
    _emit_common_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)


def _fail(handler, exc):
    status = http_status_of(exc)
    payload = {"ok": False, "code": getattr(exc, "code", "error"),
               "message": str(exc.message) if isinstance(exc, AppError) else str(exc),
               "req_id": getattr(handler, "_req_id", None)}
    _json_response(handler, status, payload)


class ApiHandler(BaseHTTPRequestHandler):
    """请求处理器：路由 + 异常兜底"""

    # 路由表： (方法, 正则) -> 处理函数
    ROUTES = []

    def __init__(self, *args, **kwargs):
        # 必须在 super().__init__() 之前设置：基类 __init__ 内部会调用
        # handle()→请求处理→send_response()→log_request()，彼时就要用这两个字段
        self._req_id = uuid.uuid4().hex[:12]
        self._req_start = time.time()
        super().__init__(*args, **kwargs)

    def log_request(self, code='-', size='-'):
        """结构化访问日志（JSON 行）：方法、路径、状态码、耗时、客户端、请求 ID

        send_response() 会以真实状态码调用本方法；handle_one_request 末尾可能
        再以无参方式调用一次（占位 '-'），此处跳过以避免重复/无意义日志。
        """
        if code == '-':
            return
        try:
            status = int(code)
        except (TypeError, ValueError):
            status = code
        rec = {
            "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "req_id": self._req_id,
            "method": self.command,
            "path": self.path.split("?")[0],
            "status": status,
            "ms": round((time.time() - self._req_start) * 1000, 1),
            "client": self.client_address[0] if self.client_address else "-",
        }
        _access_logger.info(json.dumps(rec, ensure_ascii=False))

    def _dispatch(self, method, path):
        """返回 (是否匹配, 处理函数返回值)。

        把「路由是否匹配」与「处理函数返回值」区分开：处理函数可自行
        直接写出响应（如 CSV 下载）并返回 None，匹配成功不应被判为 404。
        """
        for (m, pattern, func) in self.ROUTES:
            if m != method:
                continue
            match = pattern.match(path)
            if match:
                return True, func(self, **match.groupdict())
        return False, None

    def _route(self, method):
        """主分发：统一 try/except，异常转 JSON"""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            # CORS 预检
            if method == "OPTIONS":
                self.send_response(204)
                _emit_common_headers(self)
                self.send_header("Access-Control-Allow-Methods",
                                 "GET, POST, PUT, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers",
                                 "Content-Type, Authorization")
                self.end_headers()
                return
            # 限流（固定窗口，按客户端 IP）
            if not _rate_allowed(self):
                raise RateLimitError()
            matched, _result = self._dispatch(method, path)
            if not matched:
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
        _emit_common_headers(self)
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


@_register("GET", r"/ready")
def ready(handler):
    """就绪探针：检查数据库可达；不可达返回 503（供编排器 readiness 探测）"""
    try:
        query_one("SELECT 1")
        return _ok(handler, {"status": "ready"})
    except Exception:
        handler.send_response(503)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        _emit_common_headers(handler)
        handler.end_headers()
        handler.wfile.write(json.dumps({"ok": False, "status": "not_ready"}).encode("utf-8"))
        return None


@_register("POST", r"/api/login")
def login(handler):
    data = _read_json(handler)
    uid = user_service.login(data.get("username", ""), data.get("password", ""))
    _audit("login", uid, data.get("username", ""), "登录成功")
    access, refresh = _issue_tokens(uid)
    return _ok(handler, {"token": access, "refresh_token": refresh,
                         "user_id": uid,
                         "username": data.get("username"),
                         "is_admin": bool(user_service.is_admin(uid))})


@_register("POST", r"/api/refresh")
def refresh(handler):
    """用刷新令牌换取新的访问令牌，并轮换刷新令牌（吊销旧令牌）"""
    data = _read_json(handler)
    rt = data.get("refresh_token", "")
    uid = refresh_token_repo.validate(rt)
    if uid is None:
        raise AuthError("刷新令牌无效或已过期")
    refresh_token_repo.revoke(rt)
    access, new_refresh = _issue_tokens(uid)
    return _ok(handler, {"token": access, "refresh_token": new_refresh})


@_register("POST", r"/api/logout")
def logout(handler):
    """吊销刷新令牌（最佳努力，失败不报错）"""
    data = _read_json(handler)
    rt = data.get("refresh_token", "")
    ruid = refresh_token_repo.validate(rt) if rt else None
    if rt:
        refresh_token_repo.revoke(rt)
    _audit("logout", ruid)
    return _ok(handler, {"logged_out": True})


@_register("POST", r"/api/register")
def register(handler):
    data = _read_json(handler)
    uid = user_service.register(data.get("username", ""), data.get("password", ""),
                                data.get("security_q", ""), data.get("security_a", ""))
    _audit("register", uid, data.get("username", ""))
    return _ok(handler, {"user_id": uid}, status=201)


# ---- 账户与监管（用户自助 + 管理员）----

@_register("POST", r"/api/me/password")
def change_password(handler):
    """修改自己的密码（需原密码）"""
    uid = _require_user(handler)
    data = _read_json(handler)
    ok = user_service.modify_password(
        uid, data.get("old_password", ""), data.get("new_password", ""))
    if ok:
        _audit("change_password", uid)
    return _ok(handler, {"changed": ok})


@_register("GET", r"/api/security-question")
def security_question(handler):
    """取密保问题（找回密码前置，公开接口）"""
    qs = parse_qs(urlparse(handler.path).query)
    username = (qs.get("username") or [""])[0].strip()
    q = user_service.get_security_question(username)
    if q is None:
        raise NotFoundError("用户不存在")
    return _ok(handler, {"username": username, "question": q})


@_register("POST", r"/api/reset-password")
def reset_password(handler):
    """通过密保答案重置密码（公开接口）"""
    data = _read_json(handler)
    username = data.get("username", "")
    ok = user_service.reset_password_by_qa(
        username, data.get("answer", ""), data.get("new_password", ""))
    if ok:
        _audit("reset_password", None, username, "密保找回重置密码")
    return _ok(handler, {"reset": ok})


@_register("GET", r"/api/me/penalty")
def my_penalty(handler):
    """我的未结清罚款总额"""
    uid = _require_user(handler)
    return _ok(handler, {"unpaid_penalty": borrow_service.my_total_penalty(uid)})


@_register("GET", r"/api/users")
def list_users(handler):
    """全部用户（管理员）"""
    _require_admin(handler)
    users = [{"id": u[0], "username": u[1], "balance": u[2],
              "is_admin": bool(u[3])} for u in user_service.list_users()]
    return _ok(handler, {"users": users})


@_register("POST", r"/api/users/(?P<uid>\d+)/recharge")
def recharge_user(handler, uid):
    """给某用户充值余额（管理员）"""
    aid = _require_admin(handler)
    data = _read_json(handler)
    amount = data.get("amount")
    user_service.recharge(int(uid), amount)
    _audit("recharge", aid, "用户#%s" % uid, "充值 %s 元" % amount)
    return _ok(handler, {"balance": user_service.get_balance(int(uid))})


@_register("GET", r"/api/admin/borrows")
def admin_borrows(handler):
    """全部借阅记录（管理员监管）"""
    _require_admin(handler)
    return _ok(handler, {"borrows": borrow_service.all_borrows()})


@_register("GET", r"/api/admin/overdue")
def admin_overdue(handler):
    """全部逾期未还记录（管理员报表）"""
    _require_admin(handler)
    return _ok(handler, {"overdue": borrow_service.all_overdue()})


@_register("GET", r"/api/admin/logs")
def admin_logs(handler):
    """操作审计日志（管理员）：可按 action / user_id 过滤，含动作统计与总数"""
    _require_admin(handler)
    qs = parse_qs(urlparse(handler.path).query)
    limit = int((qs.get("limit") or ["100"])[0])
    action = (qs.get("action") or [""])[0].strip() or None
    uid_raw = (qs.get("user_id") or [""])[0].strip()
    uid_filter = int(uid_raw) if uid_raw.isdigit() else None
    logs = log_service.query(limit, action, uid_filter)
    return _ok(handler, {"logs": logs, "total": log_service.count(),
                         "stats": log_service.action_stats()})


@_register("GET", r"/api/admin/logs/export")
def admin_logs_export(handler):
    """导出操作审计日志为 CSV（管理员，可加 action/user_id/limit 过滤）"""
    _require_admin(handler)
    qs = parse_qs(urlparse(handler.path).query)
    limit = int((qs.get("limit") or ["2000"])[0])
    limit = max(1, min(limit, 5000))  # 上限保护，避免一次性导出过大
    action = (qs.get("action") or [""])[0].strip() or None
    uid_raw = (qs.get("user_id") or [""])[0].strip()
    uid_filter = int(uid_raw) if uid_raw.isdigit() else None
    _csv_response(handler, "operation_logs.csv",
                  log_service.csv_logs(action, uid_filter, limit))


# ---- 余额 / 罚款 / 规则 ----

@_register("GET", r"/api/me/balance")
def my_balance(handler):
    """我的余额"""
    uid = _require_user(handler)
    return _ok(handler, {"balance": user_service.get_balance(uid)})


@_register("POST", r"/api/me/pay-fine")
def pay_fine_ep(handler):
    """缴纳我的全部未结清罚款（从余额扣除，原子操作）"""
    uid = _require_user(handler)
    total = borrow_service.my_total_penalty(uid)
    if total <= 0:
        raise BusinessRuleError("当前没有待缴纳的罚款")
    user_service.pay_fine(uid, total)  # 余额不足时抛 BusinessRuleError(422)
    _audit("pay_fine", uid, "", "缴纳 %s 元" % round(float(total), 2))
    return _ok(handler, {"paid": round(float(total), 2),
                        "balance": user_service.get_balance(uid)})


@_register("GET", r"/api/rules")
def get_rules(handler):
    """查看借阅规则参数（borrow_limit / fine_threshold）"""
    _require_user(handler)
    return _ok(handler, rules_service.rule_config())


@_register("POST", r"/api/rules")
def set_rules(handler):
    """设置借阅规则参数（管理员）"""
    aid = _require_admin(handler)
    data = _read_json(handler)
    if "borrow_limit" in data:
        rules_service.set_borrow_limit(data["borrow_limit"])
    if "fine_threshold" in data:
        rules_service.set_fine_threshold(data["fine_threshold"])
    _audit("set_rules", aid, "", "调整借阅规则")
    return _ok(handler, rules_service.rule_config())


# ---- 图书 ----

@_register("GET", r"/api/books")
def list_books(handler):
    qs = parse_qs(urlparse(handler.path).query)
    q = (qs.get("q") or [""])[0]
    category = (qs.get("category") or [""])[0]
    # 多标签：支持重复 ?tag=a&tag=b，或 ?tags=a,b 逗号形式
    tags = qs.get("tag") or []
    if not tags and qs.get("tags"):
        tags = qs.get("tags")[0].split(",")
    tags = [t.strip() for t in tags if t.strip()]
    match = (qs.get("match") or ["any"])[0].lower()
    page = int((qs.get("page") or ["1"])[0])
    size = int((qs.get("size") or ["20"])[0])
    if tags:
        books = tag_service.filter_books(tags, match_all=(match == "all"))
    elif q:
        books = book_service.search(q)
    elif category:
        books = book_service.list_by_category(category)
    else:
        books = book_service.page(page, size)[0]
    rmap = rating_service.ratings_map()
    return _ok(handler, {"books": [_book_dict(b, rmap) for b in books]})


@_register("GET", r"/api/books/rank")
def rank_books(handler):
    qs = parse_qs(urlparse(handler.path).query)
    top_n = int((qs.get("top") or ["10"])[0])
    return _ok(handler, {"rank": book_service.hot_rank(top_n)})


@_register("GET", r"/api/books/top-rated")
def top_rated_books(handler):
    qs = parse_qs(urlparse(handler.path).query)
    top_n = int((qs.get("top") or ["10"])[0])
    return _ok(handler, {"items": rating_service.top_rated(top_n)})


@_register("GET", r"/api/tags")
def list_tags(handler):
    """全部标签及每标签被多少本书使用"""
    tags = [{"name": name, "count": cnt} for name, cnt in tag_service.all_tags()]
    return _ok(handler, {"tags": tags})


@_register("GET", r"/api/books/(?P<bid>\d+)")
def get_book(handler, bid):
    book = book_service.get_detail(int(bid))
    d = _book_dict(book)
    d["rating"] = rating_service.get_rating(int(bid), user_id=_require_user(handler))
    d["tags"] = tag_service.book_tags(int(bid))
    return _ok(handler, d)


@_register("POST", r"/api/books")
def add_book(handler):
    aid = _require_admin(handler)
    data = _read_json(handler)
    bid = book_service.add_book(data.get("title", ""), data.get("author", ""),
                                data.get("category", ""))
    _audit("add_book", aid, data.get("title", ""))
    return _ok(handler, {"id": bid}, status=201)


@_register("PUT", r"/api/books/(?P<bid>\d+)")
def update_book(handler, bid):
    aid = _require_admin(handler)
    data = _read_json(handler)
    book_service.update_book(int(bid), data.get("title", ""),
                             data.get("author", ""), data.get("category"))
    _audit("update_book", aid, data.get("title", "") or "图书#%s" % bid)
    return _ok(handler, {"updated": True})


@_register("POST", r"/api/books/(?P<bid>\d+)/tags")
def set_book_tags(handler, bid):
    aid = _require_admin(handler)
    data = _read_json(handler)
    ok, tags, msg = tag_service.set_tags(int(bid), data.get("tags", ""))
    if not ok:
        raise NotFoundError(msg)
    _audit("set_tag", aid, "图书#%s" % bid, ",".join(tags))
    return _ok(handler, {"tags": tags, "message": msg})


@_register("DELETE", r"/api/books/(?P<bid>\d+)")
def delete_book(handler, bid):
    aid = _require_admin(handler)
    book_service.delete_book(int(bid))
    _audit("delete_book", aid, "图书#%s" % bid)
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
    _audit("borrow", uid, "图书#%s" % data.get("book_id", 0), msg)
    return _ok(handler, {"message": msg})


@_register("POST", r"/api/return")
def return_book(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    penalty = borrow_service.return_book(uid, int(data.get("book_id", 0)))
    if penalty is False:
        raise NotFoundError("没有找到未归还的借阅记录")
    _audit("return", uid, "图书#%s" % data.get("book_id", 0),
           "罚款 %s 元" % penalty if penalty else "无罚款")
    return _ok(handler, {"penalty": penalty})


@_register("POST", r"/api/renew")
def renew(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    ok, msg = borrow_service.renew_book(uid, int(data.get("book_id", 0)),
                                        int(data.get("days", 7)))
    if not ok:
        raise BusinessRuleError(msg)
    _audit("renew", uid, "图书#%s" % data.get("book_id", 0), msg)
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


@_register("GET", r"/api/my/due-soon")
def my_due_soon(handler):
    """即将到期提醒（默认 3 天内，?days= 可调）"""
    uid = _require_user(handler)
    qs = parse_qs(urlparse(handler.path).query)
    days = int((qs.get("days") or ["3"])[0])
    return _ok(handler, {"items": borrow_service.due_soon_books(uid, days)})


@_register("GET", r"/api/my/stats")
def my_stats_ep(handler):
    """我的借阅统计概览"""
    uid = _require_user(handler)
    return _ok(handler, borrow_service.my_stats(uid))


@_register("GET", r"/api/books/(?P<bid>\d+)/history")
def book_history_ep(handler, bid):
    """某本书的借阅历史（需登录）"""
    _require_user(handler)
    return _ok(handler, {"history": borrow_service.book_history(int(bid))})


@_register("GET", r"/api/export/my-borrows")
def export_my_borrows(handler):
    """导出我的借阅记录为 CSV（下载）"""
    uid = _require_user(handler)
    _csv_response(handler, "my_borrows.csv", borrow_service.csv_my_borrows(uid))


@_register("GET", r"/api/export/all-borrows")
def export_all_borrows(handler):
    """导出全部借阅记录为 CSV（管理员，下载）"""
    _require_admin(handler)
    _csv_response(handler, "all_borrows.csv", borrow_service.csv_all_borrows())


# ---- 评分 ----

@_register("GET", r"/api/books/(?P<bid>\d+)/rating")
def get_rating(handler, bid):
    uid = _require_user(handler)
    return _ok(handler, rating_service.get_rating(int(bid), user_id=uid))


@_register("POST", r"/api/books/(?P<bid>\d+)/rating")
def rate(handler, bid):
    uid = _require_user(handler)
    data = _read_json(handler)
    rating_service.rate(uid, int(bid), data.get("score"), data.get("comment", ""))
    _audit("rate", uid, "图书#%s" % bid, "%s 分" % data.get("score"))
    return _ok(handler, {"rated": True})


# ---- 预约 ----

@_register("POST", r"/api/reserve")
def reserve_book(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    ok, msg = reservation_service.reserve(uid, int(data.get("book_id", 0)))
    if not ok:
        raise BusinessRuleError(msg)
    _audit("reserve", uid, "图书#%s" % data.get("book_id", 0))
    return _ok(handler, {"message": msg})


@_register("POST", r"/api/reserve/cancel")
def cancel_reserve(handler):
    uid = _require_user(handler)
    data = _read_json(handler)
    ok, msg = reservation_service.cancel(uid, int(data.get("book_id", 0)))
    if not ok:
        raise BusinessRuleError(msg)
    _audit("cancel_reserve", uid, "图书#%s" % data.get("book_id", 0))
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


# ---- 通知中心（轮询聚合）----

@_register("GET", r"/api/notifications")
def notifications(handler):
    """我的通知中心：聚合待取预约 / 即将到期 / 逾期未还，含未读计数"""
    uid = _require_user(handler)
    data = notification_service.build(uid)
    return _ok(handler, data)


@_register("POST", r"/api/notifications/read")
def notifications_read(handler):
    """标记通知已读：{keys:[...]} 指定 key，或 {all:true} 全部已读"""
    uid = _require_user(handler)
    data = _read_json(handler)
    if data.get("all"):
        keys = notification_service.current_keys(uid)
    else:
        keys = data.get("keys") or []
    if not isinstance(keys, list):
        raise ValidationError("keys 应为字符串数组")
    marked = notification_service.mark_read(uid, [str(k) for k in keys])
    return _ok(handler, {"marked": marked})


# ---- 统计 ----

@_register("GET", r"/api/stats/dashboard")
def dashboard(handler):
    return _ok(handler, book_service.dashboard())


def _book_dict(book, rmap=None):
    """把 (id, title, author, category, is_borrow) 元组转成 JSON 友好的 dict
    rmap: book_id -> (avg, count)，列表页用于附带均分（一次查询，避免 N+1）
    """
    d = {
        "id": book[0], "title": book[1], "author": book[2],
        "category": book[3], "is_borrow": bool(book[4]),
    }
    if rmap is not None:
        avg, cnt = rmap.get(book[0], (0, 0))
        d["avg"] = round(float(avg), 1) if avg else 0.0
        d["count"] = cnt
    return d


def run(host="127.0.0.1", port=8000):
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"图书管理系统 REST API 已启动：http://{host}:{port}")
    print("健康检查：curl http://%s:%s/health" % (host, port))
    print("就绪探针：curl http://%s:%s/ready" % (host, port))

    # 启动集中校验：非法数值已在导入期快速失败；此处打印非致命告警（如默认密钥）
    from core import config
    for _w in config.validate():
        print("⚠️  配置告警：", _w)

    def _handle_signal(signum, _frame):
        print("\n收到停止信号 (%s)，准备优雅停机…" % signum)
        # shutdown() 必须在 serve_forever() 所在线程之外的线程调用，否则会死锁
        threading.Thread(target=server.shutdown, daemon=True).start()

    # 注册优雅停机信号：SIGINT=Ctrl+C，SIGTERM=Docker/systemd 等编排器停止
    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (ValueError, OSError):
        # 非主线程或平台不支持信号时静默忽略
        pass

    try:
        server.serve_forever()
    finally:
        server.server_close()
        close_connection()
        print("已停止")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run(port=port)
