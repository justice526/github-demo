"""图书标签模块（向后兼容适配层）

业务逻辑在 `service/tag_service.py`。
"""

from core.db import get_conn          # 兼容旧的 from tag import get_conn
from repository import tag_repo
from service import tag_service
from service import log_service


def init_tag_table():
    """创建标签表（幂等）"""
    tag_repo.init_table()
    return True


def parse_tag_input(text):
    """把「入门, 面试必备，经典」解析成标签列表（支持中英文逗号与顿号）"""
    return tag_service.parse_input(text)


def set_book_tags(book_id, tag_names):
    """覆盖式设置某本书的标签
    :return: (ok, tags, msg)
    """
    ok, tags, msg = tag_service.set_tags(book_id, tag_names)
    if ok:
        log_service.write(None, "set_tag", f"图书#{book_id}", f"标签：{'、'.join(tags) or '（清空）'}")
    return ok, tags, msg


def add_book_tags(book_id, tag_names):
    """追加标签（保留原有）
    :return: (ok, tags, msg)
    """
    return tag_service.add_tags(book_id, tag_names)


def remove_book_tag(book_id, tag_name):
    """移除某个标签
    :return: (ok, msg)
    """
    return tag_service.remove_tag(book_id, tag_name)


def get_book_tags(book_id):
    """取某本书的标签名列表"""
    return tag_service.book_tags(book_id)


def get_tags_map():
    """批量取所有图书的标签：{book_id: [标签名, ...]}"""
    return tag_service.tags_map()


def get_all_tags():
    """全部标签及其使用图书数，**按使用数降序**
    :return: [(标签名, 图书数), ...]
    """
    return sorted(tag_service.all_tags(), key=lambda x: -x[1])


def get_books_by_tags(tag_names, match_all=False):
    """按标签筛选图书
    :param match_all: True 需全部命中，False 任一命中
    :return: [(id, title, author, category, is_borrow), ...]
    """
    return tag_service.filter_books(tag_names, match_all)


def delete_tag(tag_name):
    """删除标签及其所有关联
    :return: (ok, msg)
    """
    return tag_service.delete_tag(tag_name)


def get_tag_stat():
    """标签统计 {total, tagged_books, orphan}"""
    return tag_service.stat()


if __name__ == "__main__":
    print("tag 模块为兼容适配层，业务逻辑见 service/tag_service.py")
