"""标签业务服务层

承载标签解析、筛选匹配与标签名规范化。
"""

from core.errors import ValidationError, NotFoundError
from repository import book_repo, tag_repo

MAX_TAG_LEN = 12
# 支持的中英文分隔符
SEPARATORS = "，,、;；"


def parse_input(text):
    """把用户输入的标签串解析成去重后的标签名列表

    支持中英文逗号、顿号、分号混用，自动去空去重。
    """
    if not text:
        return []
    for sep in SEPARATORS[1:]:
        text = text.replace(sep, SEPARATORS[0])
    names, seen = [], set()
    for part in text.split(SEPARATORS[0]):
        name = part.strip()
        if not name:
            continue
        if len(name) > MAX_TAG_LEN:
            name = name[:MAX_TAG_LEN]
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def set_tags(book_id, text_or_list):
    """覆盖式设置某本书的标签

    :param text_or_list: 标签字符串或标签名列表
    :return: (ok, tags, msg) —— 与旧接口签名一致
    """
    if not book_repo.exists(book_id):
        return False, [], f"图书 #{book_id} 不存在"
    names = parse_input(text_or_list) if isinstance(text_or_list, str) \
        else [str(n).strip() for n in (text_or_list or []) if str(n).strip()]
    if not names:
        tag_repo.replace_all(book_id, [])
        return True, [], "已清空全部标签"
    tag_repo.replace_all(book_id, names)
    return True, names, f"标签已保存：{'、'.join(names)}"


def add_tags(book_id, text_or_list):
    """追加标签（保留原有）"""
    if not book_repo.exists(book_id):
        return False, [], f"图书 #{book_id} 不存在"
    names = parse_input(text_or_list) if isinstance(text_or_list, str) \
        else [str(n).strip() for n in (text_or_list or []) if str(n).strip()]
    if not names:
        return False, [], "没有可添加的标签"
    tag_repo.add_some(book_id, names)
    return True, names, f"已添加：{'、'.join(names)}"


def remove_tag(book_id, tag_name):
    """移除某个标签"""
    tag_repo.unlink_by_name(book_id, tag_name)
    return True, f"已移除标签「{tag_name}」"


def book_tags(book_id):
    """某本书的标签名列表"""
    return tag_repo.tags_of_book(book_id)


def tags_map():
    """book_id → [标签名] 映射"""
    return tag_repo.tags_map()


def all_tags():
    """全部标签：[(标签名, 被多少本书使用), ...]

    用 book_tag 的实际关联数统计，而不是用 tag 表行数 ——
    后者会把已被打散、没有书引用的标签也算进去。
    """
    if not tag_repo.tables_ready():
        return []
    counts = {}
    for tags in tag_repo.tags_map().values():
        for t in tags:
            counts[t] = counts.get(t, 0) + 1
    return [(name, counts.get(name, 0)) for name, _ in tag_repo.find_all_tags()]


def filter_books(tag_names, match_all=False):
    """按标签筛选图书

    :param match_all: True 需全部命中，False 任一命中
    """
    if not tag_names:
        return []
    return tag_repo.books_by_tags(tag_names, match_all)


def delete_tag(tag_name):
    """删除标签及其关联"""
    if tag_repo.delete_tag(tag_name) > 0:
        return True, f"标签「{tag_name}」已删除"
    return False, f"标签「{tag_name}」不存在"


def stat():
    """标签统计：{total, used, links, tagged_books}

    key 名沿用旧版，gui.py 的标签管理窗口直接取这些字段。
    另附 orphan（孤儿标签数）供清理按钮提示，不影响旧字段。
    """
    s = tag_repo.stat()
    s["orphan"] = tag_repo.count_orphans()
    return s


def purge_orphans():
    """清理没有任何图书使用的孤儿标签"""
    n = tag_repo.purge_orphans()
    return True, f"已清理 {n} 个无书使用的标签" if n else "没有需要清理的标签"
