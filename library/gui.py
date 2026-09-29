import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from book import *
from user import *
from borrow import *
from db import init_db

# ===== 浅色主题配色 =====
BG = "#eef1f6"          # 主背景
PANEL = "#ffffff"       # 面板/标题栏
ACCENT = "#3d6cf5"      # 主题蓝
ACCENT_DK = "#2f56cc"   # 主题蓝（按下）
TEXT = "#2c3e50"        # 主文字
MUTED = "#7f8c8d"       # 次要文字
LINE = "#dfe4ec"        # 分隔线
DANGER = "#e74c3c"      # 危险红
SUCCESS = "#27ae60"     # 成功绿
FONT = "微软雅黑"


class LibraryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("个人图书管理系统")
        self.root.geometry("1100x740")
        self.root.minsize(980, 660)
        self.root.configure(bg=BG)
        self.current_user_id = None
        self.page = 1          # 分页浏览状态
        self._setup_style()
        self.show_login()

    # ================= 通用样式 =================
    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", font=(FONT, 10), rowheight=26,
                        background=PANEL, fieldbackground=PANEL, foreground=TEXT)
        style.configure("Treeview.Heading", font=(FONT, 10, "bold"), background="#e6eaf2")
        style.map("Treeview", background=[("selected", "#d6e0ff")], foreground=[("selected", TEXT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=(FONT, 10), padding=[16, 8])
        style.configure("TCombobox", font=(FONT, 9))

    def _btn(self, parent, text, command, primary=False, width=None, bg=None, fg=None):
        """统一样式的按钮"""
        if primary:
            b = tk.Button(parent, text=text, command=command, bg=ACCENT, fg="white",
                          activebackground=ACCENT_DK, activeforeground="white",
                          relief="flat", cursor="hand2", font=(FONT, 9), padx=12, pady=3)
        elif bg:
            b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg or "white",
                          activebackground=bg, activeforeground=fg or "white",
                          relief="flat", cursor="hand2", font=(FONT, 9), padx=12, pady=3)
        else:
            b = tk.Button(parent, text=text, command=command, bg="#e8ecf3", fg=TEXT,
                          activebackground="#d6dde8", relief="flat", cursor="hand2",
                          font=(FONT, 9), padx=12, pady=3)
        if width:
            b.config(width=width)
        return b

    def _label(self, parent, text, size=10, bold=False, fg=TEXT, bg=BG, **kw):
        f = (FONT, size, "bold") if bold else (FONT, size)
        return tk.Label(parent, text=text, font=f, fg=fg, bg=bg, **kw)

    # ========== 登录窗口 ==========
    def show_login(self):
        self.login_win = tk.Toplevel(self.root)
        self.login_win.title("用户登录")
        self.login_win.configure(bg=PANEL)
        self.login_win.resizable(False, False)

        w, h = 360, 320
        self.login_win.update_idletasks()
        x = (self.login_win.winfo_screenwidth() - w) // 2
        y = (self.login_win.winfo_screenheight() - h) // 2
        self.login_win.geometry(f"{w}x{h}+{x}+{y}")

        self._label(self.login_win, "📚 图书管理系统", size=16, bold=True, fg=ACCENT, bg=PANEL).pack(pady=(28, 6))
        self._label(self.login_win, "Personal Library System", size=8, fg=MUTED, bg=PANEL).pack()

        frame = tk.Frame(self.login_win, bg=PANEL)
        frame.pack(pady=18)
        self._label(frame, "用户名：", bg=PANEL).grid(row=0, column=0, pady=6, sticky="e")
        self.entry_user = tk.Entry(frame, width=20, font=(FONT, 10), relief="solid", bd=1)
        self.entry_user.grid(row=0, column=1, pady=6)
        self._label(frame, "密  码：", bg=PANEL).grid(row=1, column=0, pady=6, sticky="e")
        self.entry_pwd = tk.Entry(frame, width=20, font=(FONT, 10), show="*", relief="solid", bd=1)
        self.entry_pwd.grid(row=1, column=1, pady=6)
        self.login_win.bind("<Return>", lambda e: self.do_login())

        btn_frame = tk.Frame(self.login_win, bg=PANEL)
        btn_frame.pack(pady=8)
        self._btn(btn_frame, "登 录", self.do_login, primary=True, width=10).grid(row=0, column=0, padx=6)
        self._btn(btn_frame, "注 册", self.do_register, width=10).grid(row=0, column=1, padx=6)
        self._btn(self.login_win, "忘记密码", self.forget_password, width=24).pack(pady=4)
        self._label(self.login_win, "默认管理员：admin / admin123", size=8, fg=MUTED, bg=PANEL).pack(pady=(10, 0))

    def do_login(self):
        username = self.entry_user.get().strip()
        pwd = self.entry_pwd.get().strip()
        if not username or not pwd:
            messagebox.showwarning("提示", "用户名和密码不能为空")
            return
        uid = login_user(username, pwd)
        if uid:
            self.current_user_id = uid
            role = "（管理员）" if is_admin(uid) else ""
            messagebox.showinfo("成功", f"登录成功{role}！\n当前余额：{get_balance(uid)} 元")
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
        # 顶部标题栏
        header = tk.Frame(self.root, bg=PANEL)
        header.pack(fill="x", side="top")
        self._label(header, "📚 个人图书管理系统", size=15, bold=True, fg=ACCENT, bg=PANEL).pack(side="left", padx=18, pady=12)
        self.user_label = self._label(header, "", bg=PANEL)
        self.user_label.pack(side="right", padx=18)
        tk.Frame(self.root, bg=ACCENT, height=2).pack(fill="x")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab_book = tk.Frame(self.notebook, bg=BG)
        self.tab_borrow = tk.Frame(self.notebook, bg=BG)
        self.tab_personal = tk.Frame(self.notebook, bg=BG)
        self.tab_stats = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_book, text="  图书管理  ")
        self.notebook.add(self.tab_borrow, text="  借阅管理  ")
        self.notebook.add(self.tab_personal, text="  个人中心  ")
        self.notebook.add(self.tab_stats, text="  统计报表  ")

        self.init_book_tab()
        self.init_borrow_tab()
        self.init_personal_tab()
        self.init_stats_tab()
        self.update_user_info()

    def update_user_info(self):
        bal = get_balance(self.current_user_id)
        role = "  |  👑 管理员" if is_admin(self.current_user_id) else ""
        self.user_label.config(text=f"当前用户：ID {self.current_user_id}  |  余额：{bal} 元{role}")

    # ========== 1. 图书管理标签页 ==========
    def init_book_tab(self):
        left = tk.Frame(self.tab_book, bg=BG, padx=10, pady=10)
        left.pack(side="left", fill="y")

        fields = [("图书ID：", "entry_bid"), ("书名：", "entry_title"),
                  ("作者：", "entry_author"), ("分类：", "entry_category"),
                  ("搜索关键词：", "entry_search"), ("分类筛选：", "entry_cat_filter")]
        for i, (text, attr) in enumerate(fields):
            self._label(left, text).grid(row=i, column=0, sticky="e", pady=4)
            e = tk.Entry(left, width=18, font=(FONT, 10), relief="solid", bd=1)
            e.grid(row=i, column=1, pady=4)
            setattr(self, attr, e)

        btn_group = tk.Frame(left, bg=BG)
        btn_group.grid(row=6, column=0, columnspan=2, pady=8)
        actions = [("添加图书", self.add_book_gui, True), ("修改图书", self.update_book_gui, False),
                   ("删除图书", self.delete_book_gui, False), ("关键词搜索", self.search_book_gui, False),
                   ("按分类筛选", self.filter_by_category_gui, False), ("批量导入图书", self.batch_import_book_gui, False),
                   ("恢复备份", self.restore_backup_gui, False), ("刷新全部", self.refresh_book_list, False)]
        for i, (text, cmd, primary) in enumerate(actions):
            self._btn(btn_group, text, cmd, primary=primary, width=14).grid(row=i, column=0, pady=3)

        # 排序区
        sort_frame = tk.LabelFrame(left, text=" 排序浏览 ", padx=8, pady=8, bg=BG, fg=TEXT, font=(FONT, 9))
        sort_frame.grid(row=7, column=0, columnspan=2, pady=6, sticky="we")
        self._label(sort_frame, "字段：").grid(row=0, column=0)
        self.sort_field = ttk.Combobox(sort_frame, values=["ID", "书名", "作者", "分类"], width=8, state="readonly")
        self.sort_field.set("ID")
        self.sort_field.grid(row=0, column=1, padx=3)
        self._label(sort_frame, "方式：").grid(row=0, column=2)
        self.sort_order = ttk.Combobox(sort_frame, values=["升序", "降序"], width=6, state="readonly")
        self.sort_order.set("升序")
        self.sort_order.grid(row=0, column=3, padx=3)
        self._btn(sort_frame, "排序", self.sort_books_gui, width=6).grid(row=0, column=4, padx=3)

        # 右侧图书列表
        right = tk.Frame(self.tab_book, bg=BG)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        columns = ("id", "title", "author", "category", "status")
        self.book_tree = ttk.Treeview(right, columns=columns, show="headings")
        for col, txt, w, anchor in [("id", "ID", 60, "center"), ("title", "书名", 200, None),
                                    ("author", "作者", 120, None), ("category", "分类", 110, None),
                                    ("status", "状态", 90, "center")]:
            self.book_tree.heading(col, text=txt)
            self.book_tree.column(col, width=w, anchor=anchor or "w")

        scroll = ttk.Scrollbar(right, orient="vertical", command=self.book_tree.yview)
        self.book_tree.configure(yscrollcommand=scroll.set)
        self.book_tree.pack(side="top", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # 分页栏
        page_bar = tk.Frame(right, bg=BG)
        page_bar.pack(side="bottom", fill="x", pady=6)
        self._label(page_bar, "每页").pack(side="left")
        self.entry_page_size = tk.Entry(page_bar, width=4, font=(FONT, 10), relief="solid", bd=1)
        self.entry_page_size.insert(0, "5")
        self.entry_page_size.pack(side="left", padx=3)
        self._label(page_bar, "本").pack(side="left")
        self._btn(page_bar, "上一页", self.prev_page).pack(side="left", padx=5)
        self._btn(page_bar, "下一页", self.next_page).pack(side="left", padx=5)
        self.page_label = self._label(page_bar, "")
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
            for entry, val in [(self.entry_bid, item[0]), (self.entry_title, item[1]),
                               (self.entry_author, item[2]), (self.entry_category, item[3])]:
                entry.delete(0, tk.END)
                entry.insert(0, val)

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
        try:
            bid = int(bid)
        except ValueError:
            messagebox.showerror("错误", "图书ID必须是数字")
            return
        if update_book(bid, title, author, category):
            messagebox.showinfo("成功", "修改成功")
            self.refresh_book_list()
        else:
            messagebox.showerror("错误", "修改失败，图书ID不存在")

    def delete_book_gui(self):
        bid = self.entry_bid.get().strip()
        if not bid:
            messagebox.showwarning("提示", "请选择要删除的图书")
            return
        try:
            bid = int(bid)
        except ValueError:
            messagebox.showerror("错误", "图书ID必须是数字")
            return
        if not messagebox.askyesno("确认", "确定删除该图书？"):
            return
        if delete_book(bid):
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
        for e in (self.entry_bid, self.entry_title, self.entry_author, self.entry_category):
            e.delete(0, tk.END)

    # ========== 2. 借阅管理标签页 ==========
    def init_borrow_tab(self):
        top = tk.Frame(self.tab_borrow, bg=BG, padx=10, pady=10)
        top.pack(fill="x")

        self._label(top, "图书ID：").grid(row=0, column=0, padx=5)
        self.entry_br_bid = tk.Entry(top, width=12, font=(FONT, 10), relief="solid", bd=1)
        self.entry_br_bid.grid(row=0, column=1, padx=5)
        self._btn(top, "借阅图书", self.borrow_book_gui, primary=True).grid(row=0, column=2, padx=8)
        self._btn(top, "归还图书", self.return_book_gui).grid(row=0, column=3, padx=8)

        self._label(top, "续借天数：").grid(row=0, column=4, padx=5)
        self.entry_renew_days = tk.Entry(top, width=8, font=(FONT, 10), relief="solid", bd=1)
        self.entry_renew_days.insert(0, "7")
        self.entry_renew_days.grid(row=0, column=5, padx=5)
        self._btn(top, "续借", self.renew_book_gui).grid(row=0, column=6, padx=8)
        self._btn(top, "查看逾期图书", self.show_overdue_gui).grid(row=0, column=7, padx=8)
        self._btn(top, "刷新我的借阅", self.refresh_my_borrow).grid(row=0, column=8, padx=8)

        columns = ("id", "title", "borrow_time", "deadline", "return_time", "penalty")
        self.borrow_tree = ttk.Treeview(self.tab_borrow, columns=columns, show="headings")
        for col, txt, w, anchor in [("id", "记录ID", 70, "center"), ("title", "书名", 160, None),
                                    ("borrow_time", "借阅时间", 150, "center"), ("deadline", "截止时间", 150, "center"),
                                    ("return_time", "归还时间", 150, "center"), ("penalty", "罚款(元)", 90, "center")]:
            self.borrow_tree.heading(col, text=txt)
            self.borrow_tree.column(col, width=w, anchor=anchor or "w")

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

    def _parse_bid(self, raw):
        if not raw:
            messagebox.showwarning("提示", "请输入图书ID")
            return None
        try:
            return int(raw)
        except ValueError:
            messagebox.showerror("错误", "图书ID必须是数字")
            return None

    def borrow_book_gui(self):
        bid = self._parse_bid(self.entry_br_bid.get().strip())
        if bid is None:
            return
        if borrow_book(self.current_user_id, bid):
            messagebox.showinfo("成功", "借阅成功，借阅期限7天")
            self.refresh_my_borrow()
            self.refresh_book_list()
        else:
            messagebox.showerror("错误", "借阅失败，图书不存在或已借出")

    def return_book_gui(self):
        bid = self._parse_bid(self.entry_br_bid.get().strip())
        if bid is None:
            return
        res = return_book(self.current_user_id, bid)
        if res is not False:
            messagebox.showinfo("成功", f"归还成功\n产生罚款：{res} 元")
            self.refresh_my_borrow()
            self.refresh_book_list()
            self.update_user_info()
        else:
            messagebox.showerror("错误", "归还失败，无对应借阅记录")

    def renew_book_gui(self):
        bid = self._parse_bid(self.entry_br_bid.get().strip())
        if bid is None:
            return
        days = self.entry_renew_days.get().strip()
        try:
            days = int(days) if days else 7
        except ValueError:
            messagebox.showerror("错误", "续借天数必须是整数")
            return
        res = renew_book(self.current_user_id, bid, days)
        if res:
            messagebox.showinfo("成功", f"续借成功\n新截止时间：{res}")
            self.refresh_my_borrow()
        else:
            messagebox.showerror("错误", "续借失败（未找到借阅记录或已逾期）")

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
        frame = tk.Frame(self.tab_personal, bg=BG, padx=24, pady=20)
        frame.pack(fill="both", expand=True)

        def section(r, text):
            self._label(frame, text, size=12, bold=True, fg=ACCENT).grid(row=r, column=0, columnspan=3, sticky="w", pady=(16, 6))

        # 余额充值
        section(0, "💰 余额充值")
        self._label(frame, "充值金额：").grid(row=1, column=0, pady=5, sticky="e")
        self.entry_recharge = tk.Entry(frame, width=18, font=(FONT, 10), relief="solid", bd=1)
        self.entry_recharge.grid(row=1, column=1, pady=5, sticky="w")
        self._btn(frame, "确认充值", self.recharge_gui, primary=True).grid(row=1, column=2, padx=10, sticky="w")

        # 修改密码
        section(2, "🔑 修改密码")
        self._label(frame, "旧密码：").grid(row=3, column=0, pady=5, sticky="e")
        self.entry_old_pwd = tk.Entry(frame, width=18, font=(FONT, 10), show="*", relief="solid", bd=1)
        self.entry_old_pwd.grid(row=3, column=1, pady=5, sticky="w")
        self._label(frame, "新密码：").grid(row=4, column=0, pady=5, sticky="e")
        self.entry_new_pwd = tk.Entry(frame, width=18, font=(FONT, 10), show="*", relief="solid", bd=1)
        self.entry_new_pwd.grid(row=4, column=1, pady=5, sticky="w")
        self._btn(frame, "确认修改", self.modify_pwd_gui).grid(row=4, column=2, padx=10, sticky="w")

        # 缴纳罚款
        section(5, "💸 缴纳罚款")
        self.penalty_label = self._label(frame, f"待缴罚款：{get_user_total_penalty(self.current_user_id)} 元", fg=DANGER)
        self.penalty_label.grid(row=6, column=0, columnspan=2, sticky="w", pady=5)
        self._btn(frame, "一键缴纳全部罚款", self.pay_fine_gui, bg=SUCCESS).grid(row=6, column=2, padx=10, sticky="w")

        # 数据导出
        section(7, "📤 数据导出")
        self._btn(frame, "导出借阅记录到TXT", self.export_record_gui).grid(row=8, column=0, padx=5, pady=5)
        self._btn(frame, "备份图书数据JSON", self.backup_book_gui).grid(row=8, column=1, padx=5, pady=5)

        # 管理员功能
        section(9, "👑 管理员功能")
        self._btn(frame, "查看全部用户", self.show_all_users_gui).grid(row=10, column=0, padx=5, pady=5)

        # 注销
        self._btn(frame, "注销登录", self.logout_gui, bg=DANGER).grid(row=11, column=0, columnspan=3, pady=(24, 0))

    def recharge_gui(self):
        money = self.entry_recharge.get().strip()
        try:
            money = float(money)
        except ValueError:
            messagebox.showerror("错误", "请输入有效金额")
            return
        if money <= 0:
            messagebox.showwarning("提示", "金额必须大于0")
            return
        recharge_balance(self.current_user_id, money)
        messagebox.showinfo("成功", "充值成功")
        self.update_user_info()
        self.entry_recharge.delete(0, tk.END)

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
            self.update_user_info()
            self.penalty_label.config(text=f"待缴罚款：{get_user_total_penalty(self.current_user_id)} 元")
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
        if not is_admin(self.current_user_id):
            messagebox.showwarning("权限不足", "该功能仅管理员可用")
            return
        users = get_all_users()
        if not users:
            messagebox.showinfo("全部用户", "暂无用户数据")
            return
        lines = [f"ID:{u[0]}  用户名:{u[1]}  余额:{u[2]}元  【{'管理员' if u[3] == 1 else '普通用户'}】" for u in users]
        messagebox.showinfo("全部用户（管理员）", "\n".join(lines))

    def logout_gui(self):
        if messagebox.askyesno("确认", "确定注销登录？"):
            self.current_user_id = None
            self.notebook.destroy()
            self.user_label.master.destroy()   # 销毁整个标题栏
            self.show_login()

    # ========== 4. 统计报表标签页 ==========
    def init_stats_tab(self):
        frame = tk.Frame(self.tab_stats, bg=BG, padx=20, pady=16)
        frame.pack(fill="both", expand=True)

        self._label(frame, "📊 图书统计仪表盘", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(0, 4))
        self.dash_label = self._label(frame, "", justify="left")
        self.dash_label.pack(anchor="w", pady=4)

        self._label(frame, "🔥 热门借阅排行榜", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(14, 4))
        rank_frame = tk.Frame(frame, bg=BG)
        rank_frame.pack(anchor="w")
        self._label(rank_frame, "Top").grid(row=0, column=0)
        self.entry_rank_num = tk.Entry(rank_frame, width=5, font=(FONT, 10), relief="solid", bd=1)
        self.entry_rank_num.insert(0, "5")
        self.entry_rank_num.grid(row=0, column=1, padx=5)
        self._btn(rank_frame, "查询", self.show_rank).grid(row=0, column=2, padx=5)
        self.rank_text = tk.Text(frame, height=5, width=64, font=(FONT, 9), relief="solid", bd=1)
        self.rank_text.pack(anchor="w", pady=4)

        self._label(frame, "📚 图书分类统计", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(12, 4))
        self.cat_text = tk.Text(frame, height=5, width=64, font=(FONT, 9), relief="solid", bd=1)
        self.cat_text.pack(anchor="w", pady=4)

        self._label(frame, "👤 我的借阅统计", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(12, 4))
        self.my_stats_label = self._label(frame, "", justify="left")
        self.my_stats_label.pack(anchor="w", pady=4)

        self._btn(frame, "刷新全部统计", self.refresh_all_stats, primary=True).pack(pady=14)
        self.refresh_all_stats()

    def refresh_all_stats(self):
        dash = get_book_dashboard()
        self.dash_label.config(text=f"图书总数：{dash['total_book']} 本    已借出：{dash['borrowed']} 本    在架可借：{dash['available']} 本")

        self.cat_text.delete(1.0, tk.END)
        cat_list = get_category_stat()
        if not cat_list:
            self.cat_text.insert(tk.END, "暂无图书数据")
        for c in cat_list:
            self.cat_text.insert(tk.END, f"{c['category']}：总计{c['total']}本 | 在架{c['in_stock']}本 | 借出{c['borrowed']}本\n")

        self.show_rank()
        self.show_my_stats()

    def show_rank(self):
        try:
            num = int(self.entry_rank_num.get().strip())
        except ValueError:
            return
        if num <= 0:
            return
        rank = get_hot_book_rank(num)
        self.rank_text.delete(1.0, tk.END)
        if not rank:
            self.rank_text.insert(tk.END, "暂无借阅数据")
            return
        for i, item in enumerate(rank):
            self.rank_text.insert(tk.END, f"{i + 1}. 《{item[1]}》 - {item[2]} | 借阅次数：{item[3]}\n")

    def show_my_stats(self):
        stats = get_user_borrow_stats(self.current_user_id)
        if not stats:
            text = "暂无借阅数据"
        else:
            text = (f"累计借阅：{stats['total_borrow']} 本    已归还：{stats['returned']} 本    "
                    f"未归还：{stats['unreturned']} 本\n逾期未还：{stats['overdue_count']} 本    "
                    f"累计产生罚款：{stats['total_penalty']} 元")
        self.my_stats_label.config(text=text)


def run():
    init_db()
    root = tk.Tk()
    app = LibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()
