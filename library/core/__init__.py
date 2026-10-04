"""core —— 架构底座

全栈分层架构的公共基础设施，不含任何业务逻辑。

分层约定::

    core/           底座：连接、事务、异常、返回类型
    repository/     数据访问：只写 SQL，不知道业务规则
    service/        业务逻辑：只调 repository，不出现 SQL
    原有 *.py       向后兼容适配层：签名不变，内部转调 service

导入规范：业务模块**只允许**依赖 core 与同层的其他模块，
不得跨层反向依赖（service 不能 import repository 以外的 GUI/CLI 侧模块）。
"""

from .errors import (
    AppError, ValidationError, NotFoundError, PermissionError_,
    ConflictError, BusinessRuleError, AuthError, DatabaseError,
    to_user_message, http_status_of,
)
from .result import Result

__all__ = [
    "AppError", "ValidationError", "NotFoundError", "PermissionError_",
    "ConflictError", "BusinessRuleError", "AuthError", "DatabaseError",
    "to_user_message", "http_status_of", "Result",
    "get_conn", "cursor", "transaction", "query_one", "query_all",
    "execute", "table_exists", "close_connection", "set_db_path", "get_db_path",
]

from . import db  # noqa: E402  (放在 __all__ 之后避免循环)


def get_conn():
    """兼容旧代码的 `from db import get_conn`"""
    return db.get_conn()


cursor = db.cursor
transaction = db.transaction
query_one = db.query_one
query_all = db.query_all
execute = db.execute
table_exists = db.table_exists
close_connection = db.close_connection
set_db_path = db.set_db_path
get_db_path = db.get_db_path
