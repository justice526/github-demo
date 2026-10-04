"""评分业务服务层

承载评分校验与展示文案。
"""

from core.errors import ValidationError, NotFoundError
from repository import rating_repo, book_repo

MIN_SCORE = 1
MAX_SCORE = 5


def rate(user_id, book_id, score, comment=""):
    """给图书评分（一人一书，可覆盖）

    :raises ValidationError: 分数越界
    :raises NotFoundError: 图书不存在
    """
    try:
        s = int(score)
    except (TypeError, ValueError) as e:
        raise ValidationError("评分必须是整数") from e
    if s < MIN_SCORE or s > MAX_SCORE:
        raise ValidationError(f"评分必须在 {MIN_SCORE} 到 {MAX_SCORE} 之间")
    if not book_repo.exists(book_id):
        raise NotFoundError(f"图书 #{book_id} 不存在")
    if len(comment or "") > 200:
        raise ValidationError("评论不能超过 200 字")
    rating_repo.upsert(user_id, book_id, s, (comment or "").strip())
    return True


def get_rating(book_id, user_id=None):
    """某书的评分概览

    :return: {avg, count, my_score, my_comment}
        my_score   未评分时为 None
        my_comment 未评分时为 **空串**（不是 None）——
                   gui.py 会直接把它 insert 进 Entry，None 会让 Tk 报错
    """
    avg, count = rating_repo.stats_of(book_id)
    my_score, my_comment = None, ""
    if user_id is not None:
        row = rating_repo.find_one(user_id, book_id)
        if row:
            my_score = row["score"]
            my_comment = row["comment"] or ""
    return {
        "avg": round(float(avg), 1),
        "count": count,
        "my_score": my_score,
        "my_comment": my_comment,
    }


def ratings_map():
    """book_id → (均分, 人数) 映射"""
    return {r[0]: (r[1], r[2]) for r in rating_repo.all_stats()}


def top_rated(top_n=5, min_count=1):
    """高分榜：[{book_id, title, avg, count}]"""
    out = []
    for book_id, avg, cnt in rating_repo.top_rated(top_n, min_count):
        out.append({
            "book_id": book_id,
            "title": book_repo.get_title(book_id) or f"#{book_id}",
            "avg": round(float(avg), 1),
            "count": cnt,
        })
    return out


def comments(book_id, limit=20):
    """某书的读者评论"""
    return [
        {"user_id": r[0], "username": r[1], "score": r[2],
         "comment": r[3], "create_time": r[4]}
        for r in rating_repo.comments_of(book_id, limit)
    ]


def delete_rating(user_id, book_id):
    """撤销我的评分"""
    return rating_repo.delete(user_id, book_id) > 0


def star_text(avg):
    """均分转星级文本，如 4.5 → ★★★★☆"""
    try:
        n = int(round(float(avg)))
    except (TypeError, ValueError):
        n = 0
    n = max(0, min(MAX_SCORE, n))
    return "★" * n + "☆" * (MAX_SCORE - n)
