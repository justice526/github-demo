"""图书业务服务层

承载业务规则与流程编排，只调 repository，不出现 SQL。

与旧 book.py 的差异：
- 旧实现把 SQL 写在业务函数里，本层全部下沉到 book_repo
- 跨表写入（如借阅要同时改 book 和 borrow_record）改用单事务，
  旧实现是分多次 commit，中途失败会留下不一致状态
"""

import json
import os

from core.errors import ValidationError, NotFoundError, BusinessRuleError
from core.result import Result
from repository import book_repo, borrow_repo


# ==================== 查询 ====================

def list_all():
    """全部图书"""
    return book_repo.find_all()


def search(keyword):
    """按书名或作者模糊搜索"""
    if not keyword:
        return []
    return book_repo.find_by_title_or_author(keyword)


def list_by_category(category):
    """按分类查询"""
    return book_repo.find_by_category(category)


def get_detail(book_id):
    """图书详情，不存在抛 NotFoundError"""
    book = book_repo.find_by_id(book_id)
    if not book:
        raise NotFoundError(f"图书 #{book_id} 不存在")
    return book


def page(page_no, page_size=5):
    """分页浏览"""
    return book_repo.find_page(page_no, page_size)


def sorted_books(sort_by="id", order="asc"):
    """排序浏览（字段白名单在 repo 层）"""
    return book_repo.find_sorted(sort_by, order)


def advanced_search(title_kw=None, author_kw=None, category=None, status=None,
                    sort_by="id", order="asc"):
    """多条件组合搜索"""
    return book_repo.advanced_search(title_kw, author_kw, category, status, sort_by, order)


def categories():
    """全部分类名"""
    return book_repo.all_categories()


def dashboard():
    """统计仪表盘"""
    return book_repo.dashboard()


def category_stat():
    """分类统计（返回字典列表，与旧 GUI 期望一致）"""
    return [
        {"category": r[0], "total": r[1], "in_stock": r[2], "borrowed": r[3]}
        for r in book_repo.count_by_category()
    ]


def hot_rank(top_n):
    """热门借阅排行榜"""
    return book_repo.hot_rank(top_n)


# ==================== 写操作 ====================

def add_book(title, author, category):
    """新增图书

    :raises ValidationError: 书名为空
    """
    if not title or not str(title).strip():
        raise ValidationError("书名不能为空")
    if not author or not str(author).strip():
        raise ValidationError("作者不能为空")
    if not category or not str(category).strip():
        raise ValidationError("分类不能为空")
    book_id = book_repo.insert(str(title).strip(), str(author).strip(), str(category).strip())
    return book_id


def update_book(book_id, new_title, new_author, new_category=None):
    """修改图书信息"""
    if not book_repo.exists(book_id):
        return False
    if not new_title or not str(new_title).strip():
        raise ValidationError("书名不能为空")
    return book_repo.update(book_id, str(new_title).strip(),
                            str(new_author).strip() if new_author else None,
                            new_category) > 0


def delete_book(book_id):
    """删除图书

    业务规则：存在未归还借阅时禁止删除（旧实现在这里校验，
    属于业务判断，故放在 service 而非 repo）。
    """
    if borrow_repo.count_unreturned_by_book(book_id) > 0:
        raise BusinessRuleError("该图书存在未归还的借阅记录，无法删除")
    return book_repo.delete(book_id) > 0


# ==================== 备份 / 恢复 ====================

def backup_json(save_file="book_backup.json"):
    """导出图书数据为 JSON"""
    data = book_repo.dump_all()
    try:
        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        raise ValidationError(f"备份文件写入失败：{e}") from e


def restore_json(filename, overwrite=False):
    """从 JSON 恢复图书"""
    if not os.path.exists(filename):
        raise NotFoundError(f"备份文件不存在：{filename}")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValidationError(f"备份文件解析失败：{e}") from e
    if not isinstance(data, list):
        raise ValidationError("备份文件格式不正确，应为图书列表")
    book_repo.restore(data, overwrite=overwrite)
    return True


def import_from_txt(txt_file):
    """从 txt 批量导入：一行「书名,作者,分类」

    :return: (成功数, 失败数)
    """
    if not os.path.exists(txt_file):
        return 0, 0
    success = fail = 0
    try:
        with open(txt_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return 0, 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != 3:
            fail += 1
            continue
        title, author, category = (p.strip() for p in parts)
        try:
            book_repo.insert(title, author, category)
            success += 1
        except Exception:
            fail += 1
    return success, fail
