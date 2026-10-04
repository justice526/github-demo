"""图书评分模块（向后兼容适配层）

业务逻辑在 `service/rating_service.py`。
"""

from core.db import get_conn          # 兼容旧的 from rating import get_conn
from repository import rating_repo, book_repo
from service import rating_service
from service import log_service


def init_rating_table():
    """创建评分表（幂等）"""
    rating_repo.init_table()
    return True


def rate_book(user_id, book_id, score, comment=""):
    """给图书评分（一人一书，重复评分覆盖）
    :return: True 成功 / False 失败
    """
    try:
        rating_service.rate(user_id, book_id, score, comment)
    except Exception:
        return False
    title = book_repo.get_title(book_id) or ""
    log_service.write(user_id, "rate", f"《{title}》#{book_id}",
                      f"{score} 分" + (f"｜{comment}" if comment else ""))
    return True


def get_book_rating(book_id, user_id=None):
    """某书的评分概览
    :return: {avg, count, my_score, my_comment}
    """
    return rating_service.get_rating(book_id, user_id)


def get_ratings_map():
    """book_id → (均分, 人数) 映射"""
    return rating_service.ratings_map()


def get_top_rated(top_n=5, min_count=1):
    """高分榜 [{book_id, title, avg, count}, ...]"""
    return rating_service.top_rated(top_n, min_count)


def get_book_comments(book_id, limit=20):
    """某书的读者评论 [{user_id, username, score, comment, create_time}, ...]"""
    return rating_service.comments(book_id, limit)


def delete_rating(user_id, book_id):
    """撤销我的评分"""
    return rating_service.delete_rating(user_id, book_id)


def star_text(avg):
    """均分转星级文本，如 4.5 → ★★★★☆"""
    return rating_service.star_text(avg)


if __name__ == "__main__":
    print("rating 模块为兼容适配层，业务逻辑见 service/rating_service.py")
