"""service —— 业务服务层

职责边界：
- ✅ 承载业务规则、校验、流程编排、跨模块协同
- ✅ 只调用 repository，**不出现任何 SQL**
- ❌ 不直接操作数据库连接
- ❌ 不感知 GUI / CLI / HTTP 的存在

分层依赖方向（严禁反向）::

    gui / app  →  service  →  repository  →  core
                              （适配层）    （底座）
"""

__all__ = [
    "book_service", "user_service", "borrow_service", "reservation_service",
    "rating_service", "tag_service", "log_service", "rules_service",
]
