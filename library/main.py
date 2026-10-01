"""个人图书管理系统 - 统一启动入口"""
from db import init_db
from rating import init_rating_table
from rules import init_rules_table
from reservation import init_reservation_table


def main():
    init_db()
    init_rating_table()
    init_rules_table()
    init_reservation_table()
    print("\n===== 个人图书管理系统 =====")
    print("请选择运行模式：")
    print("1. 命令行模式")
    print("2. 图形界面模式")
    choice = input("请输入 1 或 2（直接回车默认命令行）：").strip()
    if choice == "2":
        import gui
        gui.run()
    else:
        import app
        app.main()


if __name__ == "__main__":
    main()
