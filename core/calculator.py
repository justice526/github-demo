"""
SmartCalc API - 核心计算模块
负责所有基础运算逻辑
"""

def add(a: float, b: float) -> float:
    """加法"""
    return a + b

def sub(a: float, b: float) -> float:
    """减法"""
    return a - b

def mul(a: float, b: float) -> float:
    """乘法"""
    return a * b

def div(a: float, b: float) -> float:
    """除法，除数为零时抛出异常"""
    if b == 0:
        raise ZeroDivisionError("除数不能为零")
    return a / b
