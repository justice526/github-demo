"""统一返回类型

原项目的函数返回值五花八门：有的是 bool，有的是元组 `(ok, msg)`，
有的是裸列表，有的是 dict。适配层要同时兼容这些，service 层则
统一用 Result，避免 bool 丢信息（比如"为什么失败"）。

用法::

    r = Result.ok(data={"id": 7})
    if r:
        print(r.data)
    else:
        print(r.message)   # 类型化异常翻译好的文案
"""

__all__ = ["Result"]


class Result:
    """一次操作的统一结果

    成功时携带 data，失败时携带 code / message。
    `bool(r)` 直接表示成败，方便写 `if r:`。
    """

    __slots__ = ("ok", "data", "code", "message", "detail")

    def __init__(self, ok, data=None, code=None, message=None, detail=None):
        self.ok = ok
        self.data = data
        self.code = code
        self.message = message
        self.detail = detail

    # ---------- 构造 ----------
    @classmethod
    def success(cls, data=None, message=None):
        return cls(True, data=data, message=message)

    @classmethod
    def failure(cls, message, code=None, detail=None):
        return cls(False, code=code or "app_error", message=message, detail=detail)

    @classmethod
    def from_exception(cls, exc):
        """把异常翻译成失败结果

        :param exc: 任意异常，优先识别 AppError
        """
        from .errors import AppError, to_user_message
        if isinstance(exc, AppError):
            return cls(False, code=exc.code, message=exc.message, detail=exc.detail)
        return cls(False, code="app_error", message=to_user_message(exc), detail=str(exc))

    @classmethod
    def from_tuple(cls, pair, data_on_ok=None):
        """兼容旧代码的 `(ok, msg)` 元组返回值

        原项目大量函数返回 `(True, "")` 或 `(False, "书名不能为空")`，
        适配层用这个方法无损转成 Result。
        """
        try:
            ok, msg = pair
        except (TypeError, ValueError):
            return cls(False, code="bad_return",
                       message="返回值格式异常，期望 (ok, msg) 元组")
        return cls.success(data=data_on_ok) if ok else cls.failure(msg)

    # ---------- 便捷转换 ----------
    def unwrap(self, default=None):
        """取数据；失败时返回 default（不抛异常）"""
        return self.data if self.ok else default

    def to_tuple(self):
        """转回旧的 `(ok, msg)` 元组，供适配层保持向后兼容"""
        return (self.ok, self.message or "")

    def to_dict(self):
        if self.ok:
            return {"ok": True, "data": self.data}
        d = {"ok": False, "code": self.code, "message": self.message}
        if self.detail:
            d["detail"] = str(self.detail)
        return d

    # ---------- 协议方法 ----------
    def __bool__(self):
        return self.ok

    def __eq__(self, other):
        if isinstance(other, Result):
            return (self.ok == other.ok and self.data == other.data
                    and self.message == other.message)
        if isinstance(other, tuple):
            return self.to_tuple() == other
        if isinstance(other, bool):
            return self.ok == other
        return NotImplemented

    def __hash__(self):
        return hash((self.ok, self.message))

    def __repr__(self):
        if self.ok:
            return f"<Result OK data={self.data!r}>"
        return f"<Result FAIL {self.code}: {self.message}>"

    # 允许 r == (True, "") 这类旧式断言
    def __iter__(self):
        return iter(self.to_tuple())
