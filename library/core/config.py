"""集中配置：从环境变量（含 .env 文件）加载，并在启动时集中校验。

零第三方依赖：.env 用标准库手动解析，不引入 python-dotenv。

设计要点
--------
- 进程启动早期即把 .env 载入 os.environ（不覆盖已存在的真实环境变量）；
  这样 web.py 等模块用 os.environ.get 即可读到，且 .env.example → .env 的工作流可用。
- 所有配置项在此集中定义与校验；非法数值在导入期直接抛 ConfigError（快速失败）。
- 不安全默认密钥仅用于本地演示；生产必须注入强随机 JWT_SECRET（见 validate() 告警）。
"""

import os

_INSECURE_DEFAULT_SECRET = "dev-only-insecure-secret-change-me"


def _load_dotenv(path=".env"):
    """把 .env 中的 KEY=VALUE 载入 os.environ（不覆盖已存在的变量）。

    解析规则：跳过空行与 # 注释；按首个 = 切分；去除值两侧的引号包裹。
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if not k:
                    continue
                if len(v) >= 2 and v[0] in "\"'":
                    v = v[1:-1] if v[-1] == v[0] else v
                if k not in os.environ:
                    os.environ[k] = v
    except OSError:
        # 读不到 .env 不应阻断启动
        pass


_load_dotenv()


class ConfigError(Exception):
    """配置非法，应导致启动失败（fail-fast）"""


def _int(name, default, min_value=None):
    """读取整型配置；缺省用 default；非法或越界抛 ConfigError。"""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        val = int(raw)
    except ValueError:
        raise ConfigError("环境变量 %s 必须为整数，收到：%r" % (name, raw))
    if min_value is not None and val < min_value:
        raise ConfigError("环境变量 %s 必须 >= %d，收到：%d" % (name, min_value, val))
    return val


# ---- 集中定义（全部来自环境变量 / .env）----
JWT_SECRET = os.environ.get("JWT_SECRET", _INSECURE_DEFAULT_SECRET)
ACCESS_TTL = _int("ACCESS_TTL", 1800, min_value=1)        # 访问令牌寿命（秒）
REFRESH_TTL = _int("REFRESH_TTL", 604800, min_value=1)   # 刷新令牌寿命（秒，默认 7 天）
RATE_LIMIT = _int("RATE_LIMIT", 600, min_value=1)         # 单 IP 每窗口允许请求数
RATE_WINDOW = _int("RATE_WINDOW", 60, min_value=1)       # 限流窗口（秒）
# CORS 白名单（逗号分隔的源）；为空表示仅同源，不暴露跨域头（禁用通配符）
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGIN", "").split(",") if o.strip()]


def is_secret_insecure():
    """是否在使用不安全默认密钥（仅本地演示场景）"""
    return JWT_SECRET == _INSECURE_DEFAULT_SECRET


def validate():
    """集中校验，返回告警信息列表（不抛异常）。

    非法数值已在 _int 中于导入期直接抛 ConfigError（快速失败）；
    此处仅收集非致命告警（如不安全默认密钥 / 空 CORS），供 run() 打印提示。
    """
    warnings = []
    if is_secret_insecure():
        warnings.append(
            "JWT_SECRET 使用的是不安全默认密钥！生产环境必须通过环境变量注入强随机值"
            "（例如：python -c \"import secrets; print(secrets.token_urlsafe(48))\"）")
    if not CORS_ORIGINS:
        warnings.append("CORS_ORIGIN 为空：将拒绝所有跨域请求（同域/直接访问不受影响）")
    return warnings
