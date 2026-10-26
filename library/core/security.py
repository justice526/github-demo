"""密码哈希（零第三方依赖，仅用标准库）

实现要点
--------
- 算法：PBKDF2-HMAC-SHA256（hashlib.pbkdf2_hmac），每用户随机盐。
- 存储格式： ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``
- 遗留兼容：历史密码以明文存储。verify_password 把非本格式的值按明文比较，
  使既有账号无需迁移即可登录；user_service.login 成功后会就地升级为哈希。
- 比较使用 hmac.compare_digest，避免时序侧信道攻击。
"""

import hashlib
import hmac
import os

ALGO = "pbkdf2_sha256"
ITERATIONS = 200_000          # PBKDF2 迭代次数（2026 年通用强度基线）
_PRF = "sha256"
_PREFIX = ALGO + "$"


def hash_password(password):
    """对明文密码做加盐哈希，返回可存储字符串。"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(_PRF, password.encode("utf-8"), salt, ITERATIONS)
    return "%s$%d$%s$%s" % (ALGO, ITERATIONS, salt.hex(), dk.hex())


def verify_password(password, stored):
    """校验明文密码与存储值是否匹配。

    stored 为 None/空或非哈希格式时，按遗留明文比较（向后兼容）。
    """
    if not stored or not stored.startswith(_PREFIX):
        return stored == password
    try:
        _, iters_s, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            _PRF, password.encode("utf-8"),
            bytes.fromhex(salt_hex), int(iters_s))
    except Exception:
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


def is_legacy_plaintext(stored):
    """存储值是否为遗留明文（需升级为哈希）"""
    return bool(stored) and not stored.startswith(_PREFIX)
