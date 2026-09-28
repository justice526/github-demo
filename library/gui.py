import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from book import *
from user import *
from borrow import *
from db import init_db


class LibraryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("个人图书管理系统")
        self.root.geometry("1000x680")
        self.current_user_id = None
        # 分页浏览图书的状态
        self.page = 1
        self.show_login()

    # ========== 登录窗口 ==========
    def show_login(self):
        self.login_win = tk.Toplevel(self.root)
        self.login_win.title("用户登录")
        self.login_win.geometry("340x260")
        self.login_win.resizable(False, False)

        tk.Label(self.login_win, text="图书管理系统", font=("微软雅黑", 16)).pack(pady=20)

        frame = tk.Frame(self.login_win)
        frame.pack(pady=5)
        tk.Label(frame, text="用户名：", width=8).grid(row=0, column=0, pady=5)
        self.entry_user = tk.Entry(frame, width=18)
        self.entry_user.grid(row=0, column=1)

        tk.Label(frame, text="密  码：", width=8).grid(row=1, column=0, pady=5)
        self.entry_pwd = tk.Entry(frame, width=18, show="*")
        self.entry_pwd.grid(row=1, column=1)

        btn_frame = tk.Frame(self.login_win)
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="登录", width=8, command=self.do_login).grid(row=0, column=0, padx=8)
        tk.Button(btn_frame, text="注册", width=8, command=self.do_register).grid(row=0, column=1, padx=8)
        tk.Button(self.login_win, text="忘记密码", width=20, command=self.forget_password).pack(pady=3)

    def do_login(self):
        username = self.entry_user.get().strip()
        pwd = self.entry_pwd.get().strip()
        if not username or not pwd:
            messagebox.showwarning("提示", "用户名和密码不能为空")
            return
        uid = login_user(username, pwd)
        if uid:
            self.current_user_id = uid
            messagebox.showinfo("成功", f"登录成功！\n当前余额：{get_balance(uid)} 元")
            self.login_win.destroy()
            self.init_main_ui()
        else:
            messagebox.showerror("错误", "账号或密码错误")

    def do_register(self):
        username = self.entry_user.get().strip()
        pwd = self.entry_pwd.get().strip()
        if not username or not pwd:
            messagebox.showwarning("提示", "用户名和密码不能为空")
            return
        sq = simpledialog.askstring("注册", "设置密保问题（用于找回密码，可留空）：")
        sq = sq.strip() if sq else ""
        sa = ""
        if sq:
            sa = simpledialog.askstring("注册", "设置密保答案：")
            sa = sa.strip() if sa else ""
        if register_user(username, pwd, sq, sa):
            messagebox.showinfo("成功", "注册成功，请登录")
        else:
            messagebox.showerror("错误", "用户名已存在")

    def forget_password(self):
        uname = simpledialog.askstring("忘记密码", "请输入用户名：")
        if not uname:
            return
        q = get_security_question(uname.strip())
        if not q:
            messagebox.showerror("错误", "该用户不存在或未设置密保问题")
            return
        ans = simpledialog.askstring("忘记密码", f"密保问题：{q}\n请输入密保答案：")
        if ans is None:
            return
        new_pwd = simpledialog.askstring("忘记密码", "请输入新密码：")
        if not new_pwd:
            return
        if reset_password_by_qa(uname.strip(), ans.strip(), new_pwd):
            messagebox.showinfo("成功", "密码重置成功，请用新密码登录")
        else:
            messagebox.showerror("错误", "密保答案错误")

    # ========== 主界面初始化 ==========
    def init_main_ui(self):
        top_bar = tk.Frame(self.root, bg="#f0f0f0", height=40)
        top_bar.pack(fill="x", side="top")
        self.user_label = tk.Label(top_bar, text=f"当前用户：ID {self.current_user_id}  |  余额：{get_balance(self.current_user_id)} 元",
                                   bg="#f0f0f0", font=("微软雅黑", 10))
        self.user_label.pack(side="right", padx=20)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_book = tk.Frame(self.notebook)
        self.tab_borrow = tk.Frame(self.notebook)
        self.tab_personal = tk.Frame(self.notebook)
        self.tab_stats = tk.Frame(self.notebook)

        self.notebook.add(self.tab_book, text="图书管理")
        self.notebook.add(self.tab_borrow, text="借阅管理")
        self.notebook.add(self.tab_personal, text="个人中心")
        self.notebook.add(self.tab_stats, text="统计报表")

        self.init_book_tab()
        self.init_borrow_tab()
        self.init_personal_tab()
        self.init_stats_tab()

    # ========== 1. 图书管理标签页 ==========
    def init_book_tab(self):
        left = tk.Frame(self.tab_book, padx=10, pady=10)
        left.pack(side="left", fill="y")

        tk.Label(left, text="图书ID：").grid(row=0, column=0, sticky="e", pady=4)
        self.entry_bid = tk.Entry(left, width=18)
        self.entry_bid.grid(row=0, column=1, pady=4)

        tk.Label(left, text="书名：").grid(row=1, column=0, sticky="e", pady=4)
        self.entry_title = tk.Entry(left, width=18)
        self.entry_title.grid(row=1, column=1, pady=4)

        tk.Label(left, text="作者：").grid(row=2, column=0, sticky="e", pady=4)
        self.entry_author = tk.Entry(left, width=18)
        self.entry_author.grid(row=2, column=1, pady=4)

        tk.Label(left, text="分类：").grid(row=3, column=0, sticky="e", pady=4)
        self.entry_category = tk.Entry(left, width=18)
        self.entry_category.grid(row=3, column=1, pady=4)

        tk.Label(left, text="搜索关键词：").grid(row=4, column=0, sticky="e", pady=4)
        self.entry_search = tk.Entry(left, width=18)
        self.entry_search.grid(row=4, column=1, pady=4)

        tk.Label(left, text="分类筛选：").grid(row=5, column=0, sticky="e", pady=4)
        self.entry_cat_filter = tk.Entry(left, width=18)
        self.entry_cat_filter.grid(row=5, column=1, pady=4)

        btn_group = tk.Frame(left)
        btn_group.grid(row=6, column=0, columnspan=2, pady=8)
        tk.Button(btn_group, text="添加图书", width=14, command=self.add_book_gui).grid(row=0, column=0, pady=3)
        tk.Button(btn_group, text="修改图书", width=14, command=self.update_book_gui).grid(row=1, column=0, pady=3)
        tk.Button(btn_group, text="删除图书", width=14, command=self.delete_book_gui).grid(row=2, column=0, pady=3)
        tk.Button(btn_group, text="关键词搜索", width=14, command=self.search_book_gui).grid(row=3, column=0, pady=3)
        tk.Button(btn_group, text="按分类筛选", width=14, command=self.filter_by_category_gui).grid(row=4, column=0, pady=3)
        tk.Button(btn_group, text="批量导入图书", width=14, command=self.batch_import_book_gui).grid(row=5, column=0, pady=3)
        tk.Button(btn_group, text="恢复备份", width=14, command=self.restore_backup_gui).grid(row=6, column=0, pady=3)
        tk.Button(btn_group, text="刷新全部", width=14, command=self.refresh_book_list).grid(row=7, column=0, pady=3)

        # 排序区
        sort_frame = tk.LabelFrame(left, text="排序浏览", padx=6, pady=6)
        sort_frame.grid(row=7, column=0, columnspan=2, pady=6, sticky="w")
        tk.Label(sort_frame, text="字段：").grid(row=0, column=0)
        self.sort_field = ttk.Combobox(sort_frame, values=["ID", "书名", "作者", "分类"], width=8, state="readonly")
        self.sort_field.set("ID")
        self.sort_field.grid(row=0, column=1, padx=3)
        tk.Label(sort_frame, text="方式：").grid(row=0, column=2)
        self.sort_order = ttk.Combobox(sort_frame, values=["升序", "降序"], width=6, state="readonly")
        self.sort_order.set("升序")
        self.sort_order.grid(row=0, column=3, padx=3)
        tk.Button(sort_frame, text="排序", width=6, command=self.sort_books_gui).grid(row=0, column=4, padx=3)

        # 右侧图书列表
        right = tk.Frame(self.tab_book)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        columns = ("id", "title", "author", "category", "status")
        self.book_tree = ttk.Treeview(right, columns=columns, show="headings")
        self.book_tree.heading("id", text="ID")
        self.book_tree.heading("title", text="书名")
        self.book_tree.heading("author", text="作者")
        self.book_tree.heading("category", text="分类")
        self.book_tree.heading("status", text="状态")
        self.book_tree.column("id", width=50, anchor="center")
        self.book_tree.column("title", width=180)
        self.book_tree.column("author", width=100)
        self.book_tree.column("category", width=100)
        self.book_tree.column("status", width=80, anchor="center")

        scroll = ttk.Scrollbar(right, orient="vertical", command=self.book_tree.yview)
        self.book_tree.configure(yscrollcommand=scroll.set)
        self.book_tree.pack(side="top", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # 分页栏
        page_bar = tk.Frame(right)
        page_bar.pack(side="bottom", fill="x", pady=5)
        tk.Label(page_bar, text="每页").pack(side="left")
        self.entry_page_size = tk.Entry(page_bar, width=4)
        self.entry_page_size.insert(0, "5")
        self.entry_page_size.pack(side="left", padx=3)
        tk.Label(page_bar, text="本").pack(side="left")
        tk.Button(page_bar, text="上一页", command=self.prev_page).pack(side="left", padx=5)
        tk.Button(page_bar, text="下一页", command=self.next_page).pack(side="left", padx=5)
        self.page_label = tk.Label(page_bar, text="")
        self.page_label.pack(side="right", padx=10)

        self.book_tree.bind("<<TreeviewSelect>>", self.on_book_select)
        self.refresh_book_list()

    def fill_book_tree(self, books):
        for item in self.book_tree.get_children():
            self.book_tree.delete(item)
        for b in books:
            status = "已借出" if b[4] == 1 else "可借阅"
            self.book_tree.insert("", "end", values=(b[0], b[1], b[2], b[3], status))

    def refresh_book_list(self, books=None):
        if books is None:
            books = query_all_book()
        self.fill_book_tree(books)
        self.page = 1
        self.page_label.config(text=f"共 {len(books)} 本")

    def _page_size(self):
        try:
            ps = int(self.entry_page_size.get().strip())
            return ps if ps >= 1 else 5
        except ValueError:
            return 5

    def show_page(self):
        ps = self._page_size()
        books, total = get_books_by_page(self.page, ps)
        total_pages = max(1, (total + ps - 1) // ps)
        if self.page > total_pages:
            self.page = total_pages
            books, total = get_books_by_page(self.page, ps)
        self.fill_book_tree(books)
        self.page_label.config(text=f"第 {self.page}/{total_pages} 页 · 共 {total} 本")

    def prev_page(self):
        if self.page > 1:
            self.page -= 1
            self.show_page()

    def next_page(self):
        self.page += 1
        self.show_page()

    def sort_books_gui(self):
        field_map = {"ID": "id", "书名": "title", "作者": "author", "分类": "category"}
        sort_field = field_map.get(self.sort_field.get(), "id")
        sort_order = "desc" if self.sort_order.get() == "降序" else "asc"
        books = get_books_sorted(sort_field, sort_order)
        self.fill_book_tree(books)
        self.page_label.config(text=f"共 {len(books)} 本（已排序）")

    def on_book_select(self, event):
        selected = self.book_tree.selection()
        if selected:
            item = self.book_tree.item(selected[0])["values"]
            self.entry_bid.delete(0, tk.END)
            self.entry_bid.insert(0, item[0])
            self.entry_title.delete(0, tk.END)
            self.entry_title.insert(0, item[1])
            self.entry_author.delete(0, tk.END)
            self.entry_author.insert(0, item[2])
            self.entry_category.delete(0, tk.END)
            self.entry_category.insert(0, item[3])

    def add_book_gui(self):
        title = self.entry_title.get().strip()
        author = self.entry_author.get().strip()
        category = self.entry_category.get().strip()
        if not title:
            messagebox.showwarning("提示", "书名不能为空")
            return
        if add_book(title, author, category):
            messagebox.showinfo("成功", "图书添加成功")
            self.clear_book_entry()
            self.refresh_book_list()
        else:
            messagebox.showerror("错误", "添加失败")

    def update_book_gui(self):
        bid = self.entry_bid.get().strip()
        title = self.entry_title.get().strip()
        author = self.entry_author.get().strip()
        category = self.entry_category.get().strip()
        if not bid or not title:
            messagebox.showwarning("提示", "请选择图书并填写书名")
            return
        if update_book(int(bid), title, author, category):
            messagebox.showinfo("成功", "修改成功")
            self.refresh_book_list()
        else:
            messagebox.showerror("错误", "修改失败，图书ID不存在")

    def delete_book_gui(self):
        bid = self.entry_bid.get().strip()
        if not bid:
            messagebox.showwarning("提示", "请选择要删除的图书")
            return
        if not messagebox.askyesno("确认", "确定删除该图书？"):
            return
        if delete_book(int(bid)):
            messagebox.showinfo("成功", "删除成功")
            self.clear_book_entry()
            self.refresh_book_list()
        else:
            messagebox.showerror("错误", "删除失败（可能存在未归还借阅）")

    def search_book_gui(self):
        key = self.entry_search.get().strip()
        if not key:
            self.refresh_book_list()
            return
        self.fill_book_tree(search_book(key))
        self.page_label.config(text="搜索结果")

    def filter_by_category_gui(self):
        cat = self.entry_cat_filter.get().strip()
        if not cat:
            self.refresh_book_list()
            return
        self.fill_book_tree(query_book_by_category(cat))
        self.page_label.config(text=f"分类【{cat}】筛选结果")

    def batch_import_book_gui(self):
        file_path = filedialog.askopenfilename(
            title="选择图书批量导入文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
        s_cnt, f_cnt = batch_import_book_from_txt(file_path)
        messagebox.showinfo("导入完成", f"成功导入：{s_cnt} 本\n失败：{f_cnt} 本")
        self.refresh_book_list()

    def restore_backup_gui(self):
        file_path = filedialog.askopenfilename(
            title="选择备份JSON文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if not file_path:
            return
        overwrite = messagebox.askyesno("恢复模式", "选择「是」= 清空后覆盖导入\n选择「否」= 追加导入")
        if restore_books_json(file_path, overwrite=overwrite):
            messagebox.showinfo("成功", "数据恢复完成")
            self.refresh_book_list()
        else:
            messagebox.showerror("错误", "恢复失败")

    def clear_book_entry(self):
        self.entry_bid.delete(0, tk.END)
        self.entry_title.delete(0, tk.END)
        self.entry_author.delete(0, tk.END)
        self.entry_category.delete(0, tk.END)

    # ========== 2. 借阅管理标签页 ==========
    def init_borrow_tab(self):
        top = tk.Frame(self.tab_borrow, padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="图书ID：").grid(row=0, column=0, padx=5)
        self.entry_br_bid = tk.Entry(top, width=12)
        self.entry_br_bid.grid(row=0, column=1, padx=5)
        tk.Button(top, text="借阅图书", command=self.borrow_book_gui).grid(row=0, column=2, padx=8)
        tk.Button(top, text="归还图书", command=self.return_book_gui).grid(row=0, column=3, padx=8)

        tk.Label(top, text="续借天数：").grid(row=0, column=4, padx=5)
        self.entry_renew_days = tk.Entry(top, width=8)
        self.entry_renew_days.insert(0, "7")
        self.entry_renew_days.grid(row=0, column=5, padx=5)
        tk.Button(top, text="续借", command=self.renew_book_gui).grid(row=0, column=6, padx=8)
        tk.Button(top, text="查看逾期图书", command=self.show_overdue_gui).grid(row=0, column=7, padx=8)
        tk.Button(top, text="刷新我的借阅", command=self.refresh_my_borrow).grid(row=0, column=8, padx=8)

        columns = ("id", "title", "borrow_time", "deadline", "return_time", "penalty")
        self.borrow_tree = ttk.Treeview(self.tab_borrow, columns=columns, show="headings")
        self.borrow_tree.heading("id", text="记录ID")
        self.borrow_tree.heading("title", text="书名")
        self.borrow_tree.heading("borrow_time", text="借阅时间")
        self.borrow_tree.heading("deadline", text="截止时间")
        self.borrow_tree.heading("return_time", text="归还时间")
        self.borrow_tree.heading("penalty", text="罚款(元)")
        self.borrow_tree.column("id", width=70, anchor="center")
        self.borrow_tree.column("title", width=150)
        self.borrow_tree.column("borrow_time", width=140)
        self.borrow_tree.column("deadline", width=140)
        self.borrow_tree.column("return_time", width=140)
        self.borrow_tree.column("penalty", width=80, anchor="center")

        scroll = ttk.Scrollbar(self.tab_borrow, orient="vertical", command=self.borrow_tree.yview)
        self.borrow_tree.configure(yscrollcommand=scroll.set)
        self.borrow_tree.pack(fill="both", expand=True, padx=10, pady=5)
        scroll.pack(side="right", fill="y")

        self.refresh_my_borrow()

    def refresh_my_borrow(self):
        for item in self.borrow_tree.get_children():
            self.borrow_tree.delete(item)
        records = get_borrow_record(self.current_user_id)
        for r in records:
            self.borrow_tree.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4] if r[4] else "未归还", r[5]))

    def borrow_book_gui(self):
        bid = self.entry_br_bid.get().strip()
        if not bid:
            messagebox.showwarning("提示", "请输入图书ID")
            return
        if borrow_book(self.current_user_id, int(bid)):
            messagebox.showinfo("成功", "借阅成功，借阅期限7天")
            self.refresh_my_borrow()
            self.refresh_book_list()
        else:
            messagebox.showerror("错误", "借阅失败，图书不存在或已借出")

    def return_book_gui(self):
        bid = self.entry_br_bid.get().strip()
        if not bid:
            messagebox.showwarning("提示", "请输入图书ID")
            return
        res = return_book(self.current_user_id, int(bid))
        if res is not False:
            messagebox.showinfo("成功", f"归还成功\n产生罚款：{res} 元")
            self.refresh_my_borrow()
            self.refresh_book_list()
            self.update_balance_label()
        else:
            messagebox.showerror("错误", "归还失败，无对应借阅记录")

    def renew_book_gui(self):
        bid = self.entry_br_bid.get().strip()
        days = self.entry_renew_days.get().strip()
        if not bid or not days:
            messagebox.showwarning("提示", "请输入图书ID和续借天数")
            return
        try:
            days = int(days)
            res = renew_book(self.current_user_id, int(bid), days)
            if res:
                messagebox.showinfo("成功", f"续借成功\n新截止时间：{res}")
                self.refresh_my_borrow()
            else:
                messagebox.showerror("错误", "续借失败（未找到借阅记录或已逾期）")
        except ValueError:
            messagebox.showerror("错误", "天数必须是整数")

    def show_overdue_gui(self):
        overdue = get_my_overdue_books(self.current_user_id)
        if not overdue:
            messagebox.showinfo("逾期图书", "✅ 你没有逾期未还的图书")
            return
        lines = []
        total = 0
        for item in overdue:
            lines.append(f"《{item['title']}》 已逾期 {item['overdue_days']} 天 | 罚款 {item['current_penalty']} 元")
            total += item['current_penalty']
        lines.append(f"\n当前累计逾期罚款：{round(total, 2)} 元")
        messagebox.showwarning("我的逾期图书", "\n".join(lines))

    # ========== 3. 个人中心标签页 ==========
    def init_personal_tab(self):
        frame = tk.Frame(self.tab_personal, padx=20, pady=20)
        frame.pack()

        tk.Label(frame, text="余额充值", font=("微软雅黑", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=10)
        tk.Label(frame, text="充值金额：").grid(row=1, column=0, pady=5)
        self.entry_recharge = tk.Entry(frame, width=18)
        self.entry_recharge.grid(row=1, column=1, pady=5)
        tk.Button(frame, text="确认充值", command=self.recharge_gui).grid(row=1, column=2, padx=10)

        tk.Label(frame, text="修改密码", font=("微软雅黑", 12, "bold")).grid(row=2, column=0, columnspan=2, sticky="w", pady=15)
        tk.Label(frame, text="旧密码：").grid(row=3, column=0, pady=5)
        self.entry_old_pwd = tk.Entry(frame, width=18, show="*")
        self.entry_old_pwd.grid(row=3, column=1, pady=5)
        tk.Label(frame, text="新密码：").grid(row=4, column=0, pady=5)
        self.entry_new_pwd = tk.Entry(frame, width=18, show="*")
        self.entry_new_pwd.grid(row=4, column=1, pady=5)
        tk.Button(frame, text="确认修改", command=self.modify_pwd_gui).grid(row=4, column=2, padx=10)

        tk.Label(frame, text="缴纳罚款", font=("微软雅黑", 12, "bold")).grid(row=5, column=0, columnspan=2, sticky="w", pady=15)
        self.penalty_label = tk.Label(frame, text=f"待缴罚款：{get_user_total_penalty(self.current_user_id)} 元")
        self.penalty_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=5)
        tk.Button(frame, text="一键缴纳全部罚款", command=self.pay_fine_gui).grid(row=6, column=2, padx=10)

        tk.Label(frame, text="数据导出", font=("微软雅黑", 12, "bold")).grid(row=7, column=0, columnspan=2, sticky="w", pady=15)
        tk.Button(frame, text="导出借阅记录到TXT", command=self.export_record_gui).grid(row=8, column=0, padx=5)
        tk.Button(frame, text="备份图书数据JSON", command=self.backup_book_gui).grid(row=8, column=1, padx=5)

        tk.Label(frame, text="管理员功能", font=("微软雅黑", 12, "bold")).grid(row=9, column=0, columnspan=2, sticky="w", pady=15)
        tk.Button(frame, text="查看全部用户", command=self.show_all_users_gui).grid(row=10, column=0, padx=5)

        tk.Button(frame, text="注销登录", fg="red", command=self.logout_gui).grid(row=11, column=0, columnspan=3, pady=20)

    def update_balance_label(self):
        bal = get_balance(self.current_user_id)
        self.user_label.config(text=f"当前用户：ID {self.current_user_id}  |  余额：{bal} 元")
        self.penalty_label.config(text=f"待缴罚款：{get_user_total_penalty(self.current_user_id)} 元")

    def recharge_gui(self):
        money = self.entry_recharge.get().strip()
        try:
            money = float(money)
            if money <= 0:
                messagebox.showwarning("提示", "金额必须大于0")
                return
            recharge_balance(self.current_user_id, money)
            messagebox.showinfo("成功", "充值成功")
            self.update_balance_label()
            self.entry_recharge.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("错误", "请输入有效金额")

    def modify_pwd_gui(self):
        old = self.entry_old_pwd.get().strip()
        new = self.entry_new_pwd.get().strip()
        if not old or not new:
            messagebox.showwarning("提示", "密码不能为空")
            return
        if modify_password(self.current_user_id, old, new):
            messagebox.showinfo("成功", "密码修改成功")
            self.entry_old_pwd.delete(0, tk.END)
            self.entry_new_pwd.delete(0, tk.END)
        else:
            messagebox.showerror("错误", "旧密码错误")

    def pay_fine_gui(self):
        total = get_user_total_penalty(self.current_user_id)
        if total <= 0:
            messagebox.showinfo("提示", "没有待缴纳的罚款")
            return
        if not messagebox.askyesno("确认", f"确认缴纳全部 {total} 元罚款？"):
            return
        if pay_fine(self.current_user_id, total):
            messagebox.showinfo("成功", "罚款缴纳完成")
            self.update_balance_label()
        else:
            messagebox.showerror("错误", "余额不足")

    def export_record_gui(self):
        if export_borrow_record_to_txt(self.current_user_id):
            messagebox.showinfo("成功", "导出成功，文件：borrow_record.txt")
        else:
            messagebox.showerror("错误", "导出失败")

    def backup_book_gui(self):
        if backup_books_json():
            messagebox.showinfo("成功", "备份成功，文件：book_backup.json")
        else:
            messagebox.showerror("错误", "备份失败")

    def show_all_users_gui(self):
        users = get_all_users()
        if not users:
            messagebox.showinfo("全部用户", "暂无用户数据")
            return
        lines = [f"ID:{u[0]}  用户名:{u[1]}  余额:{u[2]}元" for u in users]
        messagebox.showinfo("全部用户（管理员）", "\n".join(lines))

    def logout_gui(self):
        if messagebox.askyesno("确认", "确定注销登录？"):
            self.current_user_id = None
            self.notebook.destroy()
            self.user_label.destroy()
            self.show_login()

    # ========== 4. 统计报表标签页 ==========
    def init_stats_tab(self):
        frame = tk.Frame(self.tab_stats, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="📊 图书统计仪表盘", font=("微软雅黑", 12, "bold")).pack(anchor="w", pady=5)
        self.dash_label = tk.Label(frame, text="", justify="left")
        self.dash_label.pack(anchor="w", pady=5)

        tk.Label(frame, text="🔥 热门借阅排行榜", font=("微软雅黑", 12, "bold")).pack(anchor="w", pady=(20, 5))
        rank_frame = tk.Frame(frame)
        rank_frame.pack(anchor="w")
        tk.Label(rank_frame, text="Top").grid(row=0, column=0)
        self.entry_rank_num = tk.Entry(rank_frame, width=5)
        self.entry_rank_num.insert(0, "5")
        self.entry_rank_num.grid(row=0, column=1, padx=5)
        tk.Button(rank_frame, text="查询", command=self.show_rank).grid(row=0, column=2, padx=5)
        self.rank_text = tk.Text(frame, height=6, width=60)
        self.rank_text.pack(anchor="w", pady=5)

        tk.Label(frame, text="📚 图书分类统计", font=("微软雅黑", 12, "bold")).pack(anchor="w", pady=(15, 5))
        self.cat_text = tk.Text(frame, height=6, width=60)
        self.cat_text.pack(anchor="w", pady=5)

        tk.Label(frame, text="👤 我的借阅统计", font=("微软雅黑", 12, "bold")).pack(anchor="w", pady=(15, 5))
        self.my_stats_label = tk.Label(frame, text="", justify="left")
        self.my_stats_label.pack(anchor="w", pady=5)

        tk.Button(frame, text="刷新全部统计", command=self.refresh_all_stats).pack(pady=15)
        self.refresh_all_stats()

    def refresh_all_stats(self):
        dash = get_book_dashboard()
        dash_text = f"""图书总数：{dash['total_book']} 本
已借出：{dash['borrowed']} 本
在架可借：{dash['available']} 本"""
        self.dash_label.config(text=dash_text)

        self.cat_text.delete(1.0, tk.END)
        cat_list = get_category_stat()
        for c in cat_list:
            self.cat_text.insert(tk.END, f"{c['category']}：总计{c['total']}本 | 在架{c['in_stock']}本 | 借出{c['borrowed']}本\n")

        self.show_rank()
        self.show_my_stats()

    def show_rank(self):
        try:
            num = int(self.entry_rank_num.get().strip())
            if num <= 0:
                return
            rank = get_hot_book_rank(num)
            self.rank_text.delete(1.0, tk.END)
            if not rank:
                self.rank_text.insert(tk.END, "暂无借阅数据")
                return
            for i, item in enumerate(rank):
                self.rank_text.insert(tk.END, f"{i+1}. 《{item[1]}》 - {item[2]} | 借阅次数：{item[3]}\n")
        except ValueError:
            pass

    def show_my_stats(self):
        stats = get_user_borrow_stats(self.current_user_id)
        if not stats:
            text = "暂无借阅数据"
        else:
            text = (f"累计借阅：{stats['total_borrow']} 本\n"
                    f"已归还：{stats['returned']} 本\n"
                    f"未归还：{stats['unreturned']} 本\n"
                    f"逾期未还：{stats['overdue_count']} 本\n"
                    f"累计产生罚款：{stats['total_penalty']} 元")
        self.my_stats_label.config(text=text)


def run():
    init_db()
    root = tk.Tk()
    app = LibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()
