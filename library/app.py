from book import *
from user import *
from borrow import *

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
    print("12. 模糊搜索图书")
    print("13. 导出借阅记录到txt")
    print("14. 备份图书数据JSON")
    print("15. 从JSON恢复图书备份")
    print("16. 从txt批量导入图书")
    print("17. 查看图书统计仪表盘")
    print("18. 热门借阅图书排行榜")
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
            category = input("图书分类：")
            res = add_book(title, author, category)
            if res:
                print("✅图书添加完成")
            else:
                print("❌添加失败")
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
            res = update_book(bid, new_title, new_author)
            if res:
                print("✅修改完成")
            else:
                print("❌修改失败，检查图书ID是否存在")
        elif opt == "6":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            bid = int(input("要删除的图书ID："))
            res = delete_book(bid)
            if res:
                print("✅已删除")
            else:
                print("❌删除失败，图书ID不存在")
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
        # 【修复完毕】归还图书
        elif opt == "8":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            bid = int(input("输入归还图书ID："))
            res = return_book(current_user_id, bid)
            if res is not False:
                print(f"归还成功，罚款：{res}元")
            else:
                print("归还失败，没有这条借阅记录")
        elif opt == "9":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            records = get_borrow_record(current_user_id)
            print("\n你的借阅记录：")
            for r in records:
                print(r)
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
        elif opt == "12":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            key = input("请输入书名/作者关键词搜索：")
            res_list = search_book(key)
            if len(res_list) == 0:
                print("没有找到匹配图书")
            else:
                for item in res_list:
                    print(f"id:{item[0]} 书名:{item[1]} 作者:{item[2]} 分类:{item[3]} 是否借出:{item[4]}")
        elif opt == "13":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            ok = export_borrow_record_to_txt(current_user_id)
            if ok:
                print("✅导出成功，文件：borrow_record.txt")
            else:
                print("❌导出文件失败")
        elif opt == "14":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            ok = backup_books_json()
            if ok:
                print("✅图书备份完成，生成book_backup.json")
            else:
                print("❌备份失败")
        elif opt == "15":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            fn = input("输入备份json文件名：")
            op = input("恢复模式：1=追加导入，2=清空后覆盖导入，请输入1/2：")
            ov = (op == "2")
            ok = restore_books_json(fn, overwrite=ov)
            if ok:
                print("✅数据恢复完成")
            else:
                print("❌恢复失败")
        elif opt == "16":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            txt_path = input("请输入图书txt文件名(根目录直接输入books.txt)：")
            s_cnt, f_cnt = batch_import_book_from_txt(txt_path)
            print(f"✅批量导入完成：成功{s_cnt}本，失败{f_cnt}本")
        elif opt == "17":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            dash_data = get_book_dashboard()
            print("\n==== 📊图书统计仪表盘 ====")
            print(f"图书总数：{dash_data['total_book']}")
            print(f"已借出图书：{dash_data['borrowed']}")
            print(f"在架可借图书：{dash_data['available']}")
            print("按分类统计：")
            for category, count in dash_data["category_info"]:
                print(f"  {category}：{count}本")
        elif opt == "18":
            if not current_user_id:
                print("⚠请先登录！")
                continue
            try:
                num = input("请输入要查看排行榜前几名（直接回车默认Top5）：")
                if not num.strip():
                    num = 5
                else:
                    num = int(num)
                    if num <=0:
                        print("❌数字必须大于0")
                        continue
                rank_list = get_hot_book_rank(num)
                print(f"\n====🔥热门借阅Top{num}排行榜====")
                if len(rank_list) == 0:
                    print("暂无借阅数据")
                else:
                    for idx, item in enumerate(rank_list):
                        bid, title, author, cnt = item
                        print(f"{idx+1}. 《{title}》 | {author} | 借阅次数：{cnt}")
            except ValueError:
                print("❌输入无效数字！")
        elif opt == "0":
            print("👋程序退出")
            break
        else:
            print("❌无效输入，请重新选择")

if __name__ == "__main__":
    main()