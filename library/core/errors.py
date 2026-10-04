"""类型化异常体系

全栈架构约定：业务层抛类型化异常，控制器/适配层负责翻译成
用户能看懂的文案。客户端永远看不到堆栈或内部细节。

所有异常都继承 AppError，便于调用方统一捕获。
"""

__all__ = [
    "AppError", "ValidationError", "NotFoundError", "PermissionError_",
    "ConflictError", "BusinessRuleError", "AuthError", "DatabaseError",
    "to_user_message",
]


class AppError(Exception):
    """所有业务异常的基类

    :param message: 面向用户的可读文案
    :param code:    机器可读的错误码，便于前端做差异化处理
    """

    default_code = "app_error"
    default_message = "操作失败"

    def __init__(self, message=None, code=None, detail=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.detail = detail
        super().__init__(self.message)

    def to_dict(self):
        """序列化为安全的字典（不含内部细节）"""
        d = {"ok": False, "code": self.code, "message": self.message}
        if self.detail:
            d["detail"] = str(self.detail)
        return d

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.code}: {self.message}>"


class ValidationError(AppError):
    """输入不合法：参数缺失、格式错误、超范围"""

    default_code = "validation_error"
    default_message = "输入的数据不合法"


class NotFoundError(AppError):
    """目标对象不存在：图书、用户、记录"""

    default_code = "not_found"
    default_message = "没有找到对应的记录"


# 命名冲突：Python 内置 PermissionError 是 OSError 子类，
# 这里用下划线后缀区分，业务代码 import 时用 PermissionError_ 明确指代本类。
class PermissionError_(AppError):
    """权限不足：非管理员执行管理操作、逾期禁借、欠费暂停"""

    default_code = "permission_denied"
    default_message = "没有权限执行该操作"


class ConflictError(AppError):
    """状态冲突：重复注册、重复借阅、已存在同名标签"""

    default_code = "conflict"
    default_message = "当前状态不允许该操作"


class BusinessRuleError(AppError):
    """违反业务规则：借阅超限、预约已被取消"""

    default_code = "business_rule"
    default_message = "操作不符合业务规则"


class AuthError(AppError):
    """认证失败：账号密码错误、令牌失效"""

    default_code = "auth_error"
    default_message = "账号或密码错误"


class DatabaseError(AppError):
    """数据库异常：连接失败、约束冲突、迁移失败"""

    default_code = "database_error"
    default_message = "数据库操作失败"


# 异常类型 → 建议的 HTTP 状态码，供将来的 Web 层直接复用
HTTP_STATUS = {
    ValidationError: 400,
    AuthError: 401,
    PermissionError_: 403,
    NotFoundError: 404,
    ConflictError: 409,
    BusinessRuleError: 422,
    DatabaseError: 500,
}


def to_user_message(exc):
    """把任意异常翻译成面向用户的中文文案

    保证不会把堆栈、SQL 语句等内部细节泄露给终端用户。
    """
    if isinstance(exc, AppError):
        return exc.message
    if isinstance(exc, ValueError):
        # 业务代码里大量用 ValueError 表达"参数不合法"
        return str(exc) or ValidationError.default_message
    if isinstance(exc, FileNotFoundError):
        return f"文件不存在：{exc.filename}"
    if isinstance(exc, PermissionError):
        return "没有权限访问该资源"
    if isinstance(exc, Exception):
        return f"操作失败：{type(exc).__name__}"
    return "未知错误"


def http_status_of(exc):
    """取异常对应的 HTTP 状态码，非 AppError 一律 500"""
    for cls, code in HTTP_STATUS.items():
        if isinstance(exc, cls):
            return code
    return 500
