"""
SmartCalc - 简易计算器程序入口
"""
from core.calculator import add, sub, mul, div
from core.validator import is_valid_number


def main():
    print("=== SmartCalc 简易计算器 ===")
    a_input = input("请输入第一个数字：")
    b_input = input("请输入第二个数字：")

    # 调用校验函数
    if not is_valid_number(a_input) or not is_valid_number(b_input):
        print("错误：请输入合法数字！")
        return

    a = float(a_input)
    b = float(b_input)

    print(f"加法结果：{add(a, b)}")
    print(f"减法结果：{sub(a, b)}")
    print(f"乘法结果：{mul(a, b)}")
    try:
        print(f"除法结果：{div(a, b)}")
    except ZeroDivisionError:
        print("除法错误：除数不能为0！")


if __name__ == "__main__":
    main()