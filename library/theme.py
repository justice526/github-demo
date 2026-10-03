"""GUI 主题模块：浅色 / 深色两套语义色板 + 控件树运行时重映射

设计要点
--------
1. **语义色板**：每个颜色都带语义名（bg / panel / text / warn ...），
   而不是散落的十六进制。切换主题时只需整体替换色板。
2. **模块级重绑定**：gui.py 里的 `BG` `TEXT` 等常量在 import 时被
   `from theme import *` 复制到 gui 模块的全局命名空间。切换主题时
   通过 `rebind_module_globals()` 把新色值写回 gui 模块的全局变量，
   这样后续新建的控件自动使用新配色，无需改动 190 处调用点。
3. **控件树重映射**：已创建的控件不会自动变色。`remap_widget_tree()`
   递归遍历控件树，把「旧主题色值」替换为「新主题色值」。
4. **Canvas 重绘**：Canvas 上的图元颜色独立于控件配置，单独处理
   —— 饼图 / 柱状图 / 封面 / 时间线在切换后重新绘制。

只用标准库，无第三方依赖。
"""

# ===== 语义色板 =====
# key 约定：bg=主背景  panel=面板/卡片  text=主文字  muted=次要文字
#           line=分隔线  accent=主题色  danger/success/warn=语义状态色

LIGHT = {
    "bg": "#eef1f6",
    "panel": "#ffffff",
    "text": "#2c3e50",
    "muted": "#7f8c8d",
    "line": "#dfe4ec",
    "accent": "#3d6cf5",
    "accent_dk": "#2f56cc",
    "danger": "#e74c3c",
    "success": "#27ae60",
    "warn": "#e67e22",
    # 控件专用
    "btn_bg": "#e8ecf3",
    "btn_hover": "#d6dde8",
    "entry_bg": "#ffffff",
    "tree_head": "#e6eaf2",
    "tree_head_fg": "#2c3e50",
    "tree_sel": "#d6e0ff",
    "tree_sel_fg": "#2c3e50",
    "text_bg": "#ffffff",
    "text_fg": "#2c3e50",
    "list_sel": "#d6e0ff",
    "list_sel_fg": "#2c3e50",
    # 封面绘制专用
    "cover_empty_bg": "#f4f6fa",
    "cover_empty_fg": "#c8d0dc",
    "cover_shadow": "#d9dee7",
    "cover_line": "#ffffff",
    "cover_sub": "#f2f5ff",
    "cover_id": "#e6ecff",
    "cover_on_accent": "#ffffff",
}

DARK = {
    "bg": "#141821",
    "panel": "#1e2531",
    "text": "#e6ebf5",
    "muted": "#8b97ab",
    "line": "#2e3746",
    "accent": "#5b8bff",
    "accent_dk": "#7aa3ff",
    "danger": "#ff6b5e",
    "success": "#3ddc97",
    "warn": "#ffa63d",
    # 控件专用
    "btn_bg": "#2a3342",
    "btn_hover": "#374254",
    "entry_bg": "#1a2029",
    "tree_head": "#2a3342",
    "tree_head_fg": "#e6ebf5",
    "tree_sel": "#33456b",
    "tree_sel_fg": "#ffffff",
    "text_bg": "#1a2029",
    "text_fg": "#e6ebf5",
    "list_sel": "#33456b",
    "list_sel_fg": "#ffffff",
    # 封面绘制专用（封面色块本身用彩色，白字仍可用）
    "cover_empty_bg": "#232b38",
    "cover_empty_fg": "#3d4757",
    "cover_shadow": "#0d1117",
    "cover_line": "#ffffff",
    "cover_sub": "#f2f5ff",
    "cover_id": "#e6ecff",
    "cover_on_accent": "#ffffff",
}

# 深色主题的图表色盘：整体提亮，保证在深底上有足够对比度
CHART_LIGHT = ["#3d6cf5", "#16a085", "#e67e22", "#8e44ad", "#e74c3c",
               "#2980b9", "#27ae60", "#d35400", "#7f8c8d", "#c0392b"]
CHART_DARK = ["#6f97ff", "#2fd4a8", "#ffa63d", "#b981f0", "#ff7b6e",
              "#4fb0e8", "#3ddc97", "#ff8c42", "#9aa6ba", "#ff6b81"]

THEMES = {"light": LIGHT, "dark": DARK}
CHARTS = {"light": CHART_LIGHT, "dark": CHART_DARK}

# 当前主题名，由 gui.py 在启动时设置
_current = "light"


def set_current(name):
    """设置当前主题名（仅记录，不做界面操作）"""
    global _current
    _current = name if name in THEMES else "light"


def get_current():
    return _current


def is_dark():
    return _current == "dark"


def palette():
    """返回当前主题的语义色板"""
    return THEMES[_current]


def chart_colors():
    """返回当前主题的图表色盘"""
    return CHARTS[_current]


def color(key):
    """按语义 key 取当前主题的颜色"""
    return palette().get(key, "#000000")


def build_color_map(old_name, new_name):
    """构造「旧主题色值 → 新主题色值」的重映射表

    控件树重映射的核心：只要把控件当前的 bg/fg 拿去做字典查表，
    命中就换成新色。语义相同的颜色在两套主题里key 一致，因此映射可靠。
    """
    old_p, new_p = THEMES[old_name], THEMES[new_name]
    cmap = {}
    for key in new_p:
        ov, nv = old_p.get(key), new_p[key]
        if ov and nv and ov.lower() != nv.lower():
            cmap[ov.lower()] = nv
    # 图表色盘按位置对应
    for ov, nv in zip(CHARTS[old_name], CHARTS[new_name]):
        if ov.lower() != nv.lower():
            cmap.setdefault(ov.lower(), nv)
    return cmap


def rebind_module_globals(gui_module, old_name, new_name):
    """把 gui 模块的图表色盘换到新主题，并返回重映射表

    gui.py 的其余颜色常量由自身的 `_init_palette()` 统一刷新
    （它覆盖全部语义 key），这里只处理图表色盘，避免两处逻辑重复。
    """
    gui_module.CHART_COLORS = list(CHARTS[new_name])
    return build_color_map(old_name, new_name)


# 需要检查并替换颜色的控件配置项
COLOR_OPTIONS = ("bg", "fg", "activebackground", "activeforeground",
                 "highlightbackground", "highlightcolor", "selectbackground",
                 "selectforeground", "insertbackground", "disabledforeground")


def _remap_widget(widget, cmap):
    """重映射单个控件的颜色配置"""
    if not cmap:
        return
    for opt in COLOR_OPTIONS:
        try:
            cur = widget.cget(opt)
        except Exception:
            continue
        if not isinstance(cur, str) or not cur.startswith("#"):
            continue
        new = cmap.get(cur.lower())
        if not new:
            continue
        try:
            widget.config(**{opt: new})
        except Exception:
            # ttk 控件不吃控件级颜色（由 ttk.Style 统一管），失败可忽略
            continue


def remap_widget_tree(widget, cmap):
    """递归遍历控件树，重映射所有颜色

    :param widget: 根控件（通常是 root）
    :param cmap: build_color_map 返回的映射表
    """
    if not cmap:
        return
    stack = [widget]
    count = 0
    while stack:
        w = stack.pop()
        try:
            if not w.winfo_exists():
                continue
            _remap_widget(w, cmap)
            count += 1
            stack.extend(w.winfo_children())
        except Exception:
            continue
    return count


# ===== 主题偏好持久化 =====
# 复用 rules 模块的 config 表（key, value），不额外建表。
PREF_KEY = "gui_theme"


def load_theme_pref(default="light"):
    """读取上次使用的主题；读不到或出错时返回默认值"""
    try:
        from rules import get_config
        val = get_config(PREF_KEY)
        return val if val in THEMES else default
    except Exception:
        return default


def set_theme_pref(name):
    """保存用户选择的主题"""
    try:
        from rules import set_config
        set_config(PREF_KEY, name if name in THEMES else "light")
        return True
    except Exception as e:
        print("保存主题偏好失败：", e)
        return False