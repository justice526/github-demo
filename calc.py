def add(a : int, b : int) -> int:
    return a + b

def sub(a : int, b : int) -> int:
    return a - b

def mul(a: int, b: int) -> int:
    return a * b

def div(a: int, b: int) -> float:
    return a / b

if __name__ == "__main__":
    a = eval(input())
    b = eval(input())
    print("加法：{}".format(add(a, b)))
    print("减法：{}".format(sub(a, b)))
    print("乘法：{}".format(mul(a, b)))
    print("除法：{}".format(div(a, b)))