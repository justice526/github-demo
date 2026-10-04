"""图书模块（向后兼容适配层）

**这个文件现在只是一层薄转发** —— 真正的业务逻辑在
`service/book_service.py`，数据访问在 `repository/book_repo.py`。

保留本文件的原因：gui.py 与 app.py 大量 `from book import *`，
函数签名与返回值必须一字不变，否则整个界面会崩。

适配层的两条纪律：
1. **签名与返回值必须与重构前完全一致**（含元组返回、bool 返回）
2. **异常要被翻译回旧行为** —— service 抛类型化异常，
   旧代码期待 False / (False, msg)，这里负责转换
"""

from core.errors import AppError, BusinessRuleError
from core.db import get_conn          # 兼容旧的 from book import get_conn
from repository import book_repo
from service import book_service
from service import borrow_service as _borrow_svc


# ==================== 查询 ====================

def query_all_book():
    """查询全部图书"""
    return book_service.list_all()


def search_book(keyword):
    """模糊搜索图书（书名或作者）"""
    return book_service.search(keyword)


def query_book_by_category(category):
    """按分类查询图书"""
    return book_service.list_by_category(category)


def get_all_categories():
    """库中全部已有分类名（用于下拉框）"""
    return book_service.categories()


def get_book_by_id(book_id):
    """按 ID 查单本图书，不存在返回 None"""
    return book_repo.find_by_id(book_id)


def get_book_borrow_count(book_id):
    """某本书的历史借阅次数"""
    return book_repo.borrow_count_of(book_id)


def get_current_borrower(book_id):
    """当前借阅人用户名，未借出返回 None"""
    return book_repo.current_borrower_name(book_id)


# ==================== 写操作 ====================

def add_book(title, author, category):
    """新增图书，成功返回 True"""
    try:
        book_service.add_book(title, author, category)
        return True
    except AppError:
        return False
    except Exception as e:
        print(e)
        return False


def update_book(book_id, new_title, new_author, new_category=None):
    """修改图书信息；new_category 为 None 时保持原分类不变"""
    try:
        return book_service.update_book(book_id, new_title, new_author, new_category)
    except AppError:
        return False
    except Exception as e:
        print(e)
        return False


def delete_book(book_id):
    """删除图书；存在未归还借阅则拒绝"""
    try:
        return book_service.delete_book(book_id)
    except BusinessRuleError as e:
        # 旧实现是 print + return False，保持一致
        print(f"删除失败：{e.message}")
        return False
    except AppError as e:
        print(f"删除失败：{e.message}")
        return False
    except Exception as e:
        print("删除图书异常：", e)
        return False


# ==================== 统计 ====================

def get_book_dashboard():
    """统计仪表盘"""
    return book_service.dashboard()


def get_hot_book_rank(top_n):
    """热门借阅排行榜 [(id, title, author, times), ...]"""
    return book_service.hot_rank(top_n)


def get_category_stat():
    """按分类统计 [{category, total, in_stock, borrowed}, ...]"""
    return book_service.category_stat()


def get_books_by_page(page, page_size=5):
    """分页浏览，返回 (图书列表, 总条数)"""
    return book_service.page(page, page_size)


def get_books_sorted(sort_by="id", order="asc"):
    """排序浏览全部图书"""
    return book_service.sorted_books(sort_by, order)


def get_my_overdue_books(user_id):
    """当前用户逾期未还的图书 [{record_id,title,...,overdue_days,current_penalty}]"""
    return _borrow_svc.my_overdue_books(user_id)


def advanced_search(title_kw=None, author_kw=None, category=None, status=None,
                    sort_by="id", order="asc"):
    """多条件组合搜索"""
    return book_service.advanced_search(title_kw, author_kw, category,
                                        status, sort_by, order)


# ==================== 备份 / 导入 ====================

def backup_books_json(save_file="book_backup.json"):
    """导出图书数据备份 JSON"""
    try:
        book_service.backup_json(save_file)
        return True
    except AppError as e:
        print(e.message)
        return False
    except Exception as e:
        print(e)
        return False


def restore_books_json(filename, overwrite=False):
    """从 JSON 恢复；overwrite=True 先清空原有图书"""
    try:
        book_service.restore_json(filename, overwrite)
        return True
    except AppError as e:
        print(e.message)
        return False
    except Exception as e:
        print(e)
        return False


def batch_import_book_from_txt(txt_file):
    """txt 批量导入，返回 (成功数, 失败数)"""
    return book_service.import_from_txt(txt_file)


if __name__ == "__main__":
    print("book 模块为兼容适配层，业务逻辑见 service/book_service.py")
