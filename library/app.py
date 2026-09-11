from book import add_book, query_all_book, update_book, delete_book
from user import register_user, login_user, get_balance, recharge_balance, pay_fine
from borrow import borrow_book, return_book, get_borrow_record, get_user_total_penalty

def show_menu():
    print("\n=====个人图书管理系统=====")
    print("1. 用户注册")
    print("2. 用户登录")
    print("3. 添加图书")
    print("4. 查看全部图书")
    print("5. 修改图书信息")
    print("6. 删除图书")
    print("7. 借阅图书")
    print("8. 归还图书")
    print("9. 查看我的借阅记录")
    print("10. 用户余额充值")
    print("11. 缴纳借阅罚款")
    print("0. 退出程序")
    print("==========================")

def main():
    current_user_id = None
    while True:
        show_menu()
        opt = input("请输入功能编号：")
        if opt == "1":
            username = input("输入注册用户名：")
            pwd = input("输入密码：")
            if register_user(username, pwd):
                print("✅注册成功")
            else:
                print("❌注册失败，用户名重复")
        elif opt == "2":
            username = input("输入用户名：")
            pwd = input("输入密码：")
            uid = login_user(username, pwd)
            if uid:
                current_user_id = uid
                bal = get_balance(current_user_id)
                print(f"✅登录成功，你的用户ID:{current_user_id}，当前余额：{bal}元")
            else:
                print("❌账号或密码错误")
        elif opt == "3":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            title = input("图书名称：")
            author = input("作者：")
            add_book(title, author)
            print("✅图书添加完成")
        elif opt == "4":
            books = query_all_book()
            print("\n全部图书：")
            for item in books:
                print(item)
        elif opt == "5":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            bid = int(input("要修改的图书ID："))
            new_title = input("新书名：")
            new_author = input("新作者：")
            update_book(bid, new_title, new_author)
            print("✅修改完成")
        elif opt == "6":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            bid = int(input("要删除的图书ID："))
            delete_book(bid)
            print("✅已删除")
        elif opt == "7":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            bid = int(input("要借阅的图书ID："))
            res = borrow_book(current_user_id, bid)
            if res:
                print("✅借阅成功")
            else:
                print("❌借阅失败，图书不存在或已经借出")
        elif opt == "8":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            bid = int(input("归还图书ID："))
            return_book(bid)
            print("✅归还完成")
        elif opt == "9":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            records = get_borrow_record(current_user_id)
            print("\n你的借阅记录：")
            for r in records:
                print(r)
            # 新增：展示总待缴罚款
            total_fine = get_user_total_penalty(current_user_id)
            print(f"\n💸你的待缴纳总罚款：{total_fine} 元")
        elif opt == "10":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            try:
                money = float(input("请输入充值金额："))
                recharge_balance(current_user_id, money)
                new_bal = get_balance(current_user_id)
                print(f"你的最新余额：{new_bal} 元")
            except ValueError:
                print("❌输入不是有效数字！")
        elif opt == "11":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            total_fine = get_user_total_penalty(current_user_id)
            print(f"💸待缴纳总罚款：{total_fine} 元")
            if total_fine <= 0:
                print("✅你没有需要缴纳的罚款")
                continue
            confirm = input(f"确认缴纳全部{total_fine}元罚款？(y/n):")
            if confirm.lower() == "y":
                pay_fine(current_user_id, total_fine)
                new_bal = get_balance(current_user_id)
                print(f"✅罚款缴纳完毕，当前余额：{new_bal} 元")
            else:
                print("❌取消缴费")
        elif opt == "0":
            print("👋程序退出")
            break
        else:
            print("❌无效输入，请重新选择")

if __name__ == "__main__":
    main()
