"""repository —— 数据访问层

职责边界（务必遵守）：
- ✅ 只写 SQL，只关心数据存取
- ✅ 可以互相调用（如 book_repo 查 book 表供 log 拼接标题）
- ❌ 不含业务规则（"有未归还借阅则不能删"这类判断属于 service）
- ❌ 不含用户交互、不含 GUI/CLI 概念
- ❌ 不直接被 gui.py / app.py 调用（必须经 service 层）

返回格式约定：一律返回**元组**而非 sqlite3.Row，
因为旧代码用 `row[0]` 下标访问，保持一致才不会破坏 GUI。
"""

__all__ = [
    "book_repo", "user_repo", "borrow_repo", "rating_repo",
    "rules_repo", "reservation_repo", "tag_repo", "log_repo",
]
