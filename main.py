"""
SmartCalc API - 程序入口
"""
from core.calculator import add, sub, mul, div

def main():
    print("=== SmartCalc 智能计算器 ===")
    a = float(input("请输入第一个数: "))
    b = float(input("请输入第二个数: "))

    print(f"加法: {add(a, b)}")
    print(f"减法: {sub(a, b)}")
    print(f"乘法: {mul(a, b)}")
    print(f"除法: {div(a, b)}")

if __name__ == "__main__":
    main()
