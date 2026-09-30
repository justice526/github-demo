import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from book import *
from user import *
from borrow import *
from rating import *
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

# ===== 图表 / 封面配色盘 =====
CHART_COLORS = ["#3d6cf5", "#16a085", "#e67e22", "#8e44ad", "#e74c3c",
                "#2980b9", "#27ae60", "#d35400", "#7f8c8d", "#c0392b"]


def _shade(hex_color, factor=0.75):
    """按系数加深（factor<1）或减淡（factor>1）一个十六进制颜色"""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return "#%02x%02x%02x" % (r, g, b)
    except Exception:
        return hex_color


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
        # 登录后延迟自动检查借阅到期情况
        self.root.after(400, self.auto_check_due)

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
        actions = [("🔍 高级搜索", self.advanced_search_gui, True), ("添加图书", self.add_book_gui, False),
                   ("修改图书", self.update_book_gui, False), ("删除图书", self.delete_book_gui, False),
                   ("关键词搜索", self.search_book_gui, False), ("按分类筛选", self.filter_by_category_gui, False),
                   ("图书详情", self.open_selected_detail, False), ("批量导入图书", self.batch_import_book_gui, False),
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

        # 右侧：图书列表 + 封面预览卡片
        right = tk.Frame(self.tab_book, bg=BG)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # ---- 封面预览卡片（最右侧） ----
        cover_frame = tk.Frame(right, bg=PANEL, padx=12, pady=12,
                               highlightbackground=LINE, highlightthickness=1)
        cover_frame.pack(side="right", fill="y", padx=(10, 0))
        self._label(cover_frame, "📖 封面预览", size=10, bold=True, fg=ACCENT, bg=PANEL).pack(anchor="w")
        self.cover_canvas = tk.Canvas(cover_frame, width=200, height=272, bg=PANEL,
                                      highlightthickness=0, cursor="hand2")
        self.cover_canvas.pack(pady=(8, 6))
        self.cover_info = self._label(cover_frame, "← 在左侧列表中\n   选择一本图书", size=9,
                                      fg=MUTED, bg=PANEL, justify="left", wraplength=200)
        self.cover_info.pack(anchor="w")
        self.draw_book_cover(None)

        # ---- 图书列表区 ----
        list_frame = tk.Frame(right, bg=BG)
        list_frame.pack(side="left", fill="both", expand=True)

        tree_wrap = tk.Frame(list_frame, bg=BG)
        tree_wrap.pack(side="top", fill="both", expand=True)

        columns = ("id", "title", "author", "category", "status")
        self.book_tree = ttk.Treeview(tree_wrap, columns=columns, show="headings")
        for col, txt, w, anchor in [("id", "ID", 60, "center"), ("title", "书名", 200, None),
                                    ("author", "作者", 120, None), ("category", "分类", 110, None),
                                    ("status", "状态", 90, "center")]:
            self.book_tree.heading(col, text=txt)
            self.book_tree.column(col, width=w, anchor=anchor or "w")

        scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.book_tree.yview)
        self.book_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.book_tree.pack(side="left", fill="both", expand=True)

        # 分页栏
        page_bar = tk.Frame(list_frame, bg=BG)
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
        self.book_tree.bind("<Double-1>", self.on_book_double_click)
        self.cover_canvas.bind("<Button-1>", self.on_cover_click)
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
            self.draw_book_cover(item)

    # ========== 图书详情入口 ==========
    def _selected_book_id(self):
        """取当前选中图书的 ID，未选中返回 None"""
        sel = self.book_tree.selection()
        if not sel:
            return None
        vals = self.book_tree.item(sel[0])["values"]
        try:
            return int(vals[0])
        except (ValueError, TypeError, IndexError):
            return None

    def on_book_double_click(self, event):
        """双击图书列表 → 打开详情窗口"""
        row = self.book_tree.identify_row(event.y)
        if not row:
            return
        vals = self.book_tree.item(row)["values"]
        try:
            self.show_book_detail(int(vals[0]))
        except (ValueError, TypeError, IndexError):
            pass

    def on_cover_click(self, event):
        """点击封面卡片 → 打开详情窗口"""
        bid = self._selected_book_id()
        if bid is None:
            messagebox.showinfo("提示", "请先在左侧列表中选择一本图书")
            return
        self.show_book_detail(bid)

    def open_selected_detail(self):
        """「图书详情」按钮"""
        bid = self._selected_book_id()
        if bid is None:
            messagebox.showinfo("提示", "请先在右侧列表中选择一本图书")
            return
        self.show_book_detail(bid)

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

    # ========== 图书封面卡片（Canvas 绘制） ==========
    def _wrap_text(self, text, per_line):
        """把中文长文本按每行 per_line 个字切分"""
        text = str(text or "")
        if not text:
            return [""]
        return [text[i:i + per_line] for i in range(0, len(text), per_line)]

    def _paint_cover(self, c, book, width=200, height=272):
        """把图书封面画到指定 Canvas 上（主界面与详情窗口共用）
        :param book: (id, title, author, category, status) 或 None（占位）
        """
        c.delete("all")
        if not book:
            c.create_rectangle(2, 2, width - 10, height - 10, fill="#f4f6fa", outline=LINE, dash=(4, 3))
            c.create_text(width / 2 - 2, height / 2 - 20, text="📖", font=(FONT, 26), fill="#c8d0dc")
            c.create_text(width / 2 - 2, height / 2 + 20, text="未选择图书", font=(FONT, 9), fill=MUTED)
            return

        bid, title, author, category, status = book
        # 依据分类稳定地选取封面色（不用 hash，保证同一分类颜色固定）
        idx = sum(ord(ch) for ch in str(category)) % len(CHART_COLORS)
        base = CHART_COLORS[idx]
        dark = _shade(base, 0.72)
        borrowed = str(status) in ("已借出", "1")
        right, bottom = width - 10, height - 10
        cx = (2 + right) / 2 + 8

        # 阴影 + 封面主体 + 书脊
        c.create_rectangle(6, 6, right + 4, bottom + 4, fill="#d9dee7", outline="")
        c.create_rectangle(2, 2, right, bottom, fill=base, outline="")
        c.create_rectangle(2, 2, 17, bottom, fill=dark, outline="")
        c.create_line(20, 2, 20, bottom, fill=dark, width=1)
        c.create_line(34, 42, right - 16, 42, fill="#ffffff", width=1)

        # 书名（最多 3 行自动换行）+ 作者
        lines = self._wrap_text(title, 9)[:3]
        y = 78 if len(lines) < 3 else 64
        for line in lines:
            c.create_text(cx, y, text=line, fill="#ffffff", font=(FONT, 13, "bold"))
            y += 26
        c.create_text(cx, y + 14, text=str(author or "佚名"), fill="#f2f5ff", font=(FONT, 9))

        # 底部信息区
        c.create_line(34, bottom - 46, right - 16, bottom - 46, fill="#ffffff", width=1)
        c.create_text(cx, bottom - 30, text=str(category or "未分类"), fill="#ffffff", font=(FONT, 9))
        c.create_text(cx, bottom - 12, text=f"编号 #{bid}", fill="#e6ecff", font=(FONT, 8))

        # 右上角状态角标
        tag_color = DANGER if borrowed else SUCCESS
        tag_text = "已借出" if borrowed else "在架可借"
        c.create_rectangle(right - 72, 12, right - 8, 30, fill=tag_color, outline="")
        c.create_text(right - 40, 21, text=tag_text, fill="#ffffff", font=(FONT, 8))

    def _rating_line(self, book_id):
        """生成评分文本行，例如「评分：★★★★☆ 4.5（3人）」"""
        r = get_book_rating(int(book_id), self.current_user_id)
        if r["count"] > 0:
            return f"评分：{star_text(r['avg'])} {r['avg']}（{r['count']}人）"
        return "评分：暂无评分"

    def draw_book_cover(self, book):
        """绘制主界面右侧封面卡片，并刷新下方文字信息
        :param book: (id, title, author, category, status) 或 None
        """
        self._paint_cover(self.cover_canvas, book)
        if not book:
            self.cover_info.config(text="← 在左侧列表中\n   选择一本图书", fg=MUTED)
            return
        bid, title, author, category, status = book
        borrowed = str(status) in ("已借出", "1")
        tag_text = "已借出" if borrowed else "在架可借"
        self.cover_info.config(
            text=f"《{title}》\n作者：{author or '佚名'}\n分类：{category or '未分类'}\n"
                 f"状态：{tag_text}\n{self._rating_line(bid)}\n（双击列表可查看详情）",
            fg=DANGER if borrowed else TEXT)

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
        self._btn(top, "🔔 到期提醒", self.show_due_reminder_gui, bg="#e67e22").grid(row=0, column=9, padx=8)

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

    # ========== 借阅到期提醒 ==========
    def show_due_reminder_gui(self):
        """弹窗展示：即将到期（3天内）+ 已逾期 的图书"""
        uid = self.current_user_id
        due = get_due_soon_books(uid, days=3)
        overdue = get_my_overdue_books(uid)

        if not due and not overdue:
            messagebox.showinfo("🔔 到期提醒", "✅ 太棒了！当前没有即将到期或已逾期的图书")
            return

        lines = []
        if overdue:
            lines.append("🔴 已逾期（请尽快归还，逾期每天罚款 0.5 元）：")
            for it in overdue:
                lines.append(f"   · 《{it['title']}》已逾期 {it['overdue_days']} 天，"
                             f"预计罚款 {it['current_penalty']} 元")
            lines.append("")
        if due:
            lines.append("🟡 即将到期（剩余 3 天内）：")
            for it in due:
                lines.append(f"   · 《{it['title']}》剩余约 {it['remain_days']} 天 "
                             f"（截止 {it['deadline'][:16]}）")
        messagebox.showwarning("🔔 借阅到期提醒", "\n".join(lines))

    def auto_check_due(self):
        """登录进入主界面后自动检查一次，有情况才弹窗"""
        try:
            uid = self.current_user_id
            if not uid:
                return
            due = get_due_soon_books(uid, days=3)
            overdue = get_my_overdue_books(uid)
            if not due and not overdue:
                return
            msg = f"你有 {len(due)} 本图书将在 3 天内到期，{len(overdue)} 本已逾期。\n是否查看详情？"
            if messagebox.askyesno("📢 借阅提醒", msg):
                self.show_due_reminder_gui()
        except Exception as e:
            print("自动到期检查异常：", e)

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
        self._btn(frame, "导出我的记录CSV", self.export_csv_gui).grid(row=9, column=0, padx=5, pady=5)
        self._btn(frame, "导出全库记录CSV", self.export_all_csv_gui).grid(row=9, column=1, padx=5, pady=5)

        # 管理员功能
        section(10, "👑 管理员功能")
        self._btn(frame, "查看全部用户", self.show_all_users_gui).grid(row=11, column=0, padx=5, pady=5)

        # 注销
        self._btn(frame, "注销登录", self.logout_gui, bg=DANGER).grid(row=12, column=0, columnspan=3, pady=(24, 0))

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

    def export_csv_gui(self):
        """导出我的借阅记录为 CSV（Excel 可直接打开）"""
        path = filedialog.asksaveasfilename(
            title="导出我的借阅记录为 CSV",
            defaultextension=".csv",
            initialfile="borrow_record.csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not path:
            return
        if export_borrow_record_to_csv(self.current_user_id, path):
            messagebox.showinfo("成功", f"导出成功：\n{path}")
        else:
            messagebox.showerror("错误", "导出失败")

    def export_all_csv_gui(self):
        """导出全库借阅记录为 CSV（管理员）"""
        if not is_admin(self.current_user_id):
            messagebox.showwarning("权限不足", "该功能仅管理员可用")
            return
        path = filedialog.asksaveasfilename(
            title="导出全库借阅记录为 CSV",
            defaultextension=".csv",
            initialfile="all_borrow_records.csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not path:
            return
        if export_all_borrow_to_csv(path):
            messagebox.showinfo("成功", f"导出成功：\n{path}")
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
        frame = tk.Frame(self.tab_stats, bg=BG, padx=20, pady=12)
        frame.pack(fill="both", expand=True)

        self._label(frame, "📊 图书统计仪表盘", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(0, 2))
        self.dash_label = self._label(frame, "", justify="left")
        self.dash_label.pack(anchor="w", pady=2)

        # ---- 可视化图表区（纯 Canvas 绘制，无第三方依赖） ----
        self._label(frame, "📈 数据可视化", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(8, 2))
        chart_row = tk.Frame(frame, bg=BG)
        chart_row.pack(anchor="w")

        pie_wrap = tk.Frame(chart_row, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        pie_wrap.pack(side="left")
        self.pie_canvas = tk.Canvas(pie_wrap, width=440, height=188, bg=PANEL, highlightthickness=0)
        self.pie_canvas.pack(padx=4, pady=4)

        bar_wrap = tk.Frame(chart_row, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        bar_wrap.pack(side="left", padx=(10, 0))
        self.bar_canvas = tk.Canvas(bar_wrap, width=500, height=188, bg=PANEL, highlightthickness=0)
        self.bar_canvas.pack(padx=4, pady=4)

        self._label(frame, "🔥 排行榜", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(10, 2))
        rank_frame = tk.Frame(frame, bg=BG)
        rank_frame.pack(anchor="w")
        self._label(rank_frame, "榜单：").grid(row=0, column=0)
        self.rank_type = ttk.Combobox(rank_frame, values=["借阅次数", "好评榜"], width=9, state="readonly")
        self.rank_type.set("借阅次数")
        self.rank_type.grid(row=0, column=1, padx=4)
        self._label(rank_frame, "Top").grid(row=0, column=2, padx=(8, 0))
        self.entry_rank_num = tk.Entry(rank_frame, width=5, font=(FONT, 10), relief="solid", bd=1)
        self.entry_rank_num.insert(0, "5")
        self.entry_rank_num.grid(row=0, column=3, padx=5)
        self._btn(rank_frame, "查询", self.show_rank).grid(row=0, column=4, padx=5)
        self.rank_text = tk.Text(frame, height=3, width=64, font=(FONT, 9), relief="solid", bd=1)
        self.rank_text.pack(anchor="w", pady=3)

        self._label(frame, "📚 图书分类统计", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(8, 2))
        self.cat_text = tk.Text(frame, height=3, width=64, font=(FONT, 9), relief="solid", bd=1)
        self.cat_text.pack(anchor="w", pady=3)

        self._label(frame, "👤 我的借阅统计", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(8, 2))
        self.my_stats_label = self._label(frame, "", justify="left")
        self.my_stats_label.pack(anchor="w", pady=2)

        self._btn(frame, "刷新全部统计", self.refresh_all_stats, primary=True).pack(pady=12)
        self.refresh_all_stats()

    # ========== 统计可视化图表（纯 Canvas 绘制） ==========
    def draw_category_pie(self):
        """环形图：各分类图书数量占比"""
        c = self.pie_canvas
        c.delete("all")
        stats = get_category_stat()
        data = [(s["category"] or "未分类", s["total"]) for s in stats if s["total"] > 0]
        total = sum(v for _, v in data)
        if not data or total == 0:
            c.create_text(220, 94, text="暂无图书数据", font=(FONT, 10), fill=MUTED)
            return

        cx, cy, r = 92, 94, 68
        start = 90.0
        for i, (label, val) in enumerate(data):
            extent = -360.0 * val / total
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=start, extent=extent,
                         fill=CHART_COLORS[i % len(CHART_COLORS)], outline=PANEL, width=2,
                         style="pieslice")
            start += extent
        # 中心镂空成环形
        c.create_oval(cx - 36, cy - 36, cx + 36, cy + 36, fill=PANEL, outline="")
        c.create_text(cx, cy - 6, text=str(total), font=(FONT, 14, "bold"), fill=TEXT)
        c.create_text(cx, cy + 14, text="总藏书", font=(FONT, 8), fill=MUTED)

        # 图例（两列排布）
        for i, (label, val) in enumerate(data):
            col = 176 + (i % 2) * 132
            row = i // 2
            y = 20 + row * 20
            color = CHART_COLORS[i % len(CHART_COLORS)]
            c.create_rectangle(col, y - 5, col + 10, y + 5, fill=color, outline="")
            c.create_text(col + 15, y, anchor="w", font=(FONT, 7), fill=TEXT,
                          text=f"{label[:4]} {val}本 {val * 100 // total}%")

    def draw_stock_bar(self):
        """堆叠柱状图：各分类在架 / 借出数量对比"""
        c = self.bar_canvas
        c.delete("all")
        stats = get_category_stat()
        if not stats:
            c.create_text(250, 94, text="暂无图书数据", font=(FONT, 10), fill=MUTED)
            return

        left, bottom, top, right = 34, 150, 28, 476
        max_v = max(s["total"] for s in stats) or 1
        # 网格线与纵轴刻度
        for k in range(1, 5):
            y = bottom - (bottom - top) * k / 4
            c.create_line(left, y, right, y, fill="#eef1f6")
            c.create_text(left - 5, y, text=str(round(max_v * k / 4)), anchor="e",
                          font=(FONT, 7), fill=MUTED)
        c.create_line(left, top - 8, left, bottom, fill=LINE)
        c.create_line(left, bottom, right, bottom, fill=LINE)

        n = len(stats)
        slot = (right - left) / max(n, 1)
        bar_w = min(26, slot * 0.5)
        for i, s in enumerate(stats):
            cx = left + slot * (i + 0.5)
            h_stock = (bottom - top) * s["in_stock"] / max_v
            h_borrow = (bottom - top) * s["borrowed"] / max_v
            # 在架（蓝，底部）
            if h_stock > 0:
                c.create_rectangle(cx - bar_w / 2, bottom - h_stock, cx + bar_w / 2, bottom,
                                   fill=ACCENT, outline="")
            # 借出（橙，堆叠在上）
            if h_borrow > 0:
                c.create_rectangle(cx - bar_w / 2, bottom - h_stock - h_borrow,
                                   cx + bar_w / 2, bottom - h_stock, fill="#e67e22", outline="")
            c.create_text(cx, bottom + 12, text=(s["category"] or "未分类")[:4],
                          font=(FONT, 7), fill=MUTED)
            if s["total"] > 0:
                c.create_text(cx, bottom - h_stock - h_borrow - 8, text=str(s["total"]),
                              font=(FONT, 7, "bold"), fill=TEXT)

        # 图例
        c.create_rectangle(right - 118, 10, right - 108, 20, fill=ACCENT, outline="")
        c.create_text(right - 102, 15, text="在架", anchor="w", font=(FONT, 8), fill=TEXT)
        c.create_rectangle(right - 62, 10, right - 52, 20, fill="#e67e22", outline="")
        c.create_text(right - 46, 15, text="借出", anchor="w", font=(FONT, 8), fill=TEXT)

    def refresh_all_stats(self):
        dash = get_book_dashboard()
        self.dash_label.config(text=f"图书总数：{dash['total_book']} 本    已借出：{dash['borrowed']} 本    在架可借：{dash['available']} 本")

        self.cat_text.delete(1.0, tk.END)
        cat_list = get_category_stat()
        if not cat_list:
            self.cat_text.insert(tk.END, "暂无图书数据")
        for c in cat_list:
            self.cat_text.insert(tk.END, f"{c['category']}：总计{c['total']}本 | 在架{c['in_stock']}本 | 借出{c['borrowed']}本\n")

        # 刷新两张图表
        self.draw_category_pie()
        self.draw_stock_bar()

        self.show_rank()
        self.show_my_stats()

    def show_rank(self):
        try:
            num = int(self.entry_rank_num.get().strip())
        except ValueError:
            return
        if num <= 0:
            return
        self.rank_text.delete(1.0, tk.END)

        # 好评榜：按读者平均评分排序
        if self.rank_type.get() == "好评榜":
            rows = get_top_rated(num)
            if not rows:
                self.rank_text.insert(tk.END, "暂无评分数据（可在图书详情窗口中为图书打分）")
                return
            for i, item in enumerate(rows):
                self.rank_text.insert(
                    tk.END,
                    f"{i + 1}. 《{item[1]}》 - {item[2]} | {star_text(item[3])} {item[3]} 分（{item[4]} 人评）\n")
            return

        # 借阅榜：按被借阅次数排序
        rank = get_hot_book_rank(num)
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

    # ========== 图书详情窗口 ==========
    def show_book_detail(self, book_id):
        """图书详情：封面 + 基本信息 + 我的评分 + 读者评论 + 借阅历史 + 快捷操作"""
        book = get_book_by_id(book_id)
        if not book:
            messagebox.showerror("错误", "图书不存在或已被删除")
            return
        bid, title, author, category, is_borrow = book
        status = "已借出" if is_borrow == 1 else "在架可借"

        win = tk.Toplevel(self.root)
        win.title(f"图书详情 - 《{title}》")
        win.configure(bg=BG)
        win.geometry("820x640")
        win.minsize(760, 580)
        win.transient(self.root)

        body = tk.Frame(win, bg=BG, padx=16, pady=14)
        body.pack(fill="both", expand=True)

        # ---- 左侧：封面 ----
        left = tk.Frame(body, bg=PANEL, padx=12, pady=12,
                        highlightbackground=LINE, highlightthickness=1)
        left.pack(side="left", fill="y")
        cv = tk.Canvas(left, width=200, height=272, bg=PANEL, highlightthickness=0)
        cv.pack()
        self._paint_cover(cv, (bid, title, author, category, status))
        self._label(left, self._rating_line(bid), size=9, fg=MUTED, bg=PANEL).pack(anchor="w", pady=(8, 0))

        # ---- 右侧：信息 / 评分 / 评论 / 历史 ----
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))

        self._label(right, "📘 基本信息", size=12, bold=True, fg=ACCENT).pack(anchor="w")
        info = tk.Frame(right, bg=BG)
        info.pack(anchor="w", pady=4)
        borrower = get_current_borrower(bid)
        info_rows = [
            ("图书编号", f"#{bid}"),
            ("书名", title),
            ("作者", author or "佚名"),
            ("分类", category or "未分类"),
            ("当前状态", status + (f"（借阅人：{borrower}）" if borrower else "")),
            ("历史借阅", f"{get_book_borrow_count(bid)} 次"),
        ]
        for i, (k, v) in enumerate(info_rows):
            self._label(info, k + "：", size=9, fg=MUTED).grid(row=i, column=0, sticky="e", pady=1)
            self._label(info, str(v), size=9).grid(row=i, column=1, sticky="w", padx=6, pady=1)

        # ---- 我的评分 ----
        self._label(right, "⭐ 我的评分", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(10, 2))
        my = get_book_rating(bid, self.current_user_id)
        rate_row = tk.Frame(right, bg=BG)
        rate_row.pack(anchor="w")
        self._label(rate_row, "打分：").pack(side="left")
        score_var = tk.StringVar(value=str(int(my["my_score"])) if my["my_score"] else "5")
        ttk.Combobox(rate_row, textvariable=score_var, width=3, state="readonly",
                     values=["1", "2", "3", "4", "5"]).pack(side="left", padx=4)
        self._label(rate_row, " 评论：").pack(side="left")
        comment_entry = tk.Entry(rate_row, width=26, font=(FONT, 9), relief="solid", bd=1)
        comment_entry.insert(0, my["my_comment"])
        comment_entry.pack(side="left", padx=4)

        def submit_rating():
            if rate_book(self.current_user_id, bid, score_var.get(), comment_entry.get().strip()):
                messagebox.showinfo("成功", "评分已保存", parent=win)
                win.destroy()
                self.refresh_book_list()
                self.show_book_detail(bid)
            else:
                messagebox.showerror("错误", "评分失败（分数需在 1~5 之间）", parent=win)

        self._btn(rate_row, "提交评分", submit_rating, primary=True).pack(side="left", padx=4)

        # ---- 读者评论 ----
        comments = get_book_comments(bid, 3)
        if comments:
            cmt = "\n".join(f"· {u or '匿名'}（{s}分）：{c}" for u, s, c, t in comments)
            self._label(right, "💬 读者评论\n" + cmt, size=9, fg=MUTED,
                        justify="left", wraplength=500).pack(anchor="w", pady=(6, 0))

        # ---- 借阅历史 ----
        self._label(right, "📜 借阅历史", size=12, bold=True, fg=ACCENT).pack(anchor="w", pady=(10, 2))
        hist_cols = ("user", "borrow_time", "deadline", "return_time", "penalty")
        hist = ttk.Treeview(right, columns=hist_cols, show="headings", height=5)
        for col, txt, w, anchor in [("user", "借阅人", 80, None), ("borrow_time", "借阅时间", 125, "center"),
                                    ("deadline", "应还时间", 125, "center"), ("return_time", "归还时间", 125, "center"),
                                    ("penalty", "罚款", 55, "center")]:
            hist.heading(col, text=txt)
            hist.column(col, width=w, anchor=anchor or "w")
        for h in get_book_borrow_history(bid, 20):
            hist.insert("", "end", values=(h[0] or "已注销用户", h[1], h[2],
                                           h[3] if h[3] else "未归还", h[4] or 0))
        if not hist.get_children():
            hist.insert("", "end", values=("暂无借阅记录", "", "", "", ""))
        hist.pack(fill="both", expand=True, pady=(0, 8))

        # ---- 快捷操作 ----
        btns = tk.Frame(right, bg=BG)
        btns.pack(anchor="w")

        def do_borrow():
            if borrow_book(self.current_user_id, bid):
                messagebox.showinfo("成功", "借阅成功，借期 7 天", parent=win)
                win.destroy()
                self.refresh_book_list()
                self.refresh_my_borrow()
            else:
                messagebox.showerror("错误", "借阅失败，图书不存在或已被借出", parent=win)

        def do_return():
            res = return_book(self.current_user_id, bid)
            if res is not False:
                messagebox.showinfo("成功", f"归还成功\n产生罚款：{res} 元", parent=win)
                win.destroy()
                self.refresh_book_list()
                self.refresh_my_borrow()
                self.update_user_info()
            else:
                messagebox.showerror("错误", "归还失败，你没有这本书的未归还记录", parent=win)

        self._btn(btns, "借阅本书", do_borrow, primary=True).pack(side="left", padx=3)
        btn_ret = self._btn(btns, "归还本书", do_return, bg=SUCCESS)
        btn_ret.pack(side="left", padx=3)
        if get_my_current_borrow(self.current_user_id, bid) is None:
            btn_ret.config(state="disabled")
        self._btn(btns, "关闭", win.destroy).pack(side="left", padx=3)

    # ========== 高级组合搜索窗口 ==========
    def advanced_search_gui(self):
        """书名 + 作者 + 分类 + 状态 多条件组合搜索"""
        win = tk.Toplevel(self.root)
        win.title("高级搜索")
        win.configure(bg=BG)
        win.geometry("440x370")
        win.resizable(False, False)
        win.transient(self.root)

        f = tk.Frame(win, bg=BG, padx=22, pady=16)
        f.pack(fill="both", expand=True)

        self._label(f, "🔍 多条件组合搜索", size=12, bold=True, fg=ACCENT).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self._label(f, "书名包含：").grid(row=1, column=0, sticky="e", pady=5)
        e_title = tk.Entry(f, width=22, font=(FONT, 10), relief="solid", bd=1)
        e_title.grid(row=1, column=1, pady=5, sticky="w")

        self._label(f, "作者包含：").grid(row=2, column=0, sticky="e", pady=5)
        e_author = tk.Entry(f, width=22, font=(FONT, 10), relief="solid", bd=1)
        e_author.grid(row=2, column=1, pady=5, sticky="w")

        self._label(f, "分类：").grid(row=3, column=0, sticky="e", pady=5)
        cb_cat = ttk.Combobox(f, values=["不限"] + get_all_categories(), width=20, state="readonly")
        cb_cat.set("不限")
        cb_cat.grid(row=3, column=1, pady=5, sticky="w")

        self._label(f, "状态：").grid(row=4, column=0, sticky="e", pady=5)
        cb_status = ttk.Combobox(f, values=["不限", "在架可借", "已借出"], width=20, state="readonly")
        cb_status.set("不限")
        cb_status.grid(row=4, column=1, pady=5, sticky="w")

        self._label(f, "排序：").grid(row=5, column=0, sticky="e", pady=5)
        sort_row = tk.Frame(f, bg=BG)
        sort_row.grid(row=5, column=1, sticky="w", pady=5)
        cb_sort = ttk.Combobox(sort_row, values=["ID", "书名", "作者", "分类"], width=8, state="readonly")
        cb_sort.set("ID")
        cb_sort.pack(side="left")
        cb_order = ttk.Combobox(sort_row, values=["升序", "降序"], width=6, state="readonly")
        cb_order.set("升序")
        cb_order.pack(side="left", padx=6)

        def do_search():
            field_map = {"ID": "id", "书名": "title", "作者": "author", "分类": "category"}
            status_map = {"不限": None, "在架可借": 0, "已借出": 1}
            cat = cb_cat.get()
            result = advanced_search(
                title_kw=e_title.get().strip() or None,
                author_kw=e_author.get().strip() or None,
                category=None if cat == "不限" else cat,
                status=status_map.get(cb_status.get()),
                sort_by=field_map.get(cb_sort.get(), "id"),
                order="desc" if cb_order.get() == "降序" else "asc",
            )
            self.fill_book_tree(result)
            self.page_label.config(text=f"高级搜索：命中 {len(result)} 本")
            win.destroy()

        def do_reset():
            for e in (e_title, e_author):
                e.delete(0, tk.END)
            cb_cat.set("不限")
            cb_status.set("不限")
            cb_sort.set("ID")
            cb_order.set("升序")

        btns = tk.Frame(f, bg=BG)
        btns.grid(row=6, column=0, columnspan=2, pady=18)
        self._btn(btns, "开始搜索", do_search, primary=True, width=10).pack(side="left", padx=6)
        self._btn(btns, "重置条件", do_reset, width=10).pack(side="left", padx=6)
        self._btn(btns, "关闭", win.destroy, width=8).pack(side="left", padx=6)


def run():
    init_db()
    init_rating_table()
    root = tk.Tk()
    app = LibraryApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()
