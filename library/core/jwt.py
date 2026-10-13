"""纯标准库实现的极简 JWT（HS256），零第三方依赖。

仅用于本项目演示与教学：对称签名（服务端密钥）+ 短时效访问令牌。
生产环境应配合刷新令牌、密钥轮换与 HTTPS 传输。
"""
import base64
import hashlib
import hmac
import json
import time


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(header_b64: str, payload_b64: str, secret: str) -> str:
    msg = (header_b64 + "." + payload_b64).encode("utf-8")
    mac = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return _b64url_encode(mac)


def encode(payload: dict, secret: str, ttl: int = 1800) -> str:
    """签发 JWT，自动注入 iat / exp。ttl 单位秒。"""
    now = int(time.time())
    body = dict(payload)
    body["iat"] = now
    body["exp"] = now + int(ttl)
    header = _b64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(
        json.dumps(body, separators=(",", ":")).encode("utf-8"))
    sig = _sign(header, payload_b64, secret)
    return header + "." + payload_b64 + "." + sig


def decode(token: str, secret: str) -> dict:
    """校验签名与有效期，返回 payload；失败抛 ValueError。"""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token format")
    header_b64, payload_b64, sig = parts
    expected = _sign(header_b64, payload_b64, secret)
    if not hmac.compare_digest(expected, sig):   # 恒定时间比较，防时序攻击
        raise ValueError("signature mismatch")
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        raise ValueError("payload decode error")
    exp = payload.get("exp")
    if exp is not None and int(time.time()) > int(exp):
        raise ValueError("token expired")
    return payload
