"""B 提供给 C 的三个内部业务函数（契约 7.3）。

这些是 Python 函数，不是 HTTP 接口：C 在自己的事务里调用它们。
被调用方不得自行提交事务——本文件只改对象、不 commit。

- get_post_for_claim(post_id, lock)：取信息与发布者，可加行锁；
- set_handover_state(post_id, transition)：reserve / complete / reopen；
- list_match_candidates(source_post)：按公开可见性与硬条件返回候选。
"""
import unicodedata
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from common.exceptions import ApiError
from integration.users import get_user_summary
from posts.models import Post
from posts.presenters import post_summary
from workflow.transitions import transit

MATCH_MAX_GAP = timedelta(days=30)
MATCH_NEAR_GAP = timedelta(hours=72)
MATCH_LIMIT_MAX = 20


def get_post_for_claim(post_id, lock: bool = False) -> dict:
    queryset = Post.objects.select_related("category", "campus", "location")
    if lock:
        queryset = queryset.select_for_update()
    post = queryset.filter(pk=post_id).first()
    if post is None:
        raise ApiError(404, "NOT_FOUND", "信息不存在")
    return {
        "post": post,
        "post_id": str(post.id),
        "publisher_id": post.publisher_id,
        "publisher": get_user_summary(post.publisher_id)
        or {
            "id": post.publisher_id,
            "nickname": post.publisher_nickname,
            "is_campus_verified": post.publisher_is_campus_verified,
            "verification_mode": post.publisher_verification_mode or None,
        },
    }


def set_handover_state(post_id, transition: str, actor=None) -> Post:
    """C 驱动交接状态；只接受 reserve / complete / reopen。"""
    matrix = {
        "reserve": (Post.STATUS_OPEN, Post.STATUS_IN_HANDOVER),
        "complete": (Post.STATUS_IN_HANDOVER, Post.STATUS_COMPLETED),
        "reopen": (Post.STATUS_IN_HANDOVER, Post.STATUS_OPEN),
    }
    if transition not in matrix:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "交接状态迁移只接受 reserve/complete/reopen",
            {"transition": [f"不支持的状态迁移: {transition}"]},
        )

    with transaction.atomic():
        post = Post.objects.select_for_update().filter(pk=post_id).first()
        if post is None:
            raise ApiError(404, "NOT_FOUND", "信息不存在")

        expected_from, target = matrix[transition]
        if post.status != expected_from:
            raise ApiError(
                409,
                "STATE_CONFLICT",
                f"信息当前状态为 {post.status}，不能执行 {transition}",
                {"status": [f"期望 {expected_from}，实际 {post.status}"]},
            )
        actor_id = getattr(actor, "user_id", None) or (str(actor) if actor else "c:claim-service")
        transit(post, target, actor_id, reason=f"c:{transition}")
        return post


def _normalize_title(title: str) -> str:
    """小写化、去掉空白与标点，用于 2 字连续片段比较（契约 6.3）。"""
    lowered = title.lower()
    keep = []
    for char in lowered:
        category = unicodedata.category(char)
        if category.startswith("P") or category.startswith("Z") or category.startswith("S"):
            continue
        keep.append(char)
    return "".join(keep)


def _has_common_bigram(left: str, right: str) -> bool:
    if len(left) < 2 or len(right) < 2:
        return False
    grams = {left[i:i + 2] for i in range(len(left) - 1)}
    return any(right[i:i + 2] in grams for i in range(len(right) - 1))


def _score(source: Post, candidate: Post) -> tuple[int, list[str]]:
    score = 40  # 同类别是硬条件，满足即 40 分
    reasons = ["category_same"]

    if source.location_id == candidate.location_id:
        score += 30
        reasons.append("location_same")

    if source.post_type == Post.POST_TYPE_LOST:
        lost, found = source, candidate
    else:
        lost, found = candidate, source
    gap = found.occurred_at - lost.occurred_at
    if gap <= MATCH_NEAR_GAP:
        score += 20
        reasons.append("time_near")

    if _has_common_bigram(_normalize_title(source.title), _normalize_title(candidate.title)):
        score += 10
        reasons.append("keyword_overlap")
    return score, reasons


def list_match_candidates(source_post: Post, limit: int | None = None) -> list[dict]:
    """候选硬条件：反类型、同校区、同类别、open、非本人、拾获不早于丢失且 ≤30 天。"""
    if limit is not None:
        limit = max(1, min(int(limit), MATCH_LIMIT_MAX))
    else:
        limit = MATCH_LIMIT_MAX

    opposite = (
        Post.POST_TYPE_FOUND if source_post.post_type == Post.POST_TYPE_LOST else Post.POST_TYPE_LOST
    )
    queryset = (
        Post.objects.filter(
            status=Post.STATUS_OPEN,
            post_type=opposite,
            campus_id=source_post.campus_id,
            category_id=source_post.category_id,
        )
        .exclude(publisher_id=source_post.publisher_id)
        .select_related("category", "campus", "location")
        .prefetch_related("images")
    )

    candidates = []
    now = timezone.now()
    for candidate in queryset:
        if source_post.post_type == Post.POST_TYPE_LOST:
            lost, found = source_post, candidate
        else:
            lost, found = candidate, source_post
        gap = found.occurred_at - lost.occurred_at
        if gap < timedelta(0) or gap > MATCH_MAX_GAP:
            continue
        score, reasons = _score(source_post, candidate)
        candidates.append(
            {
                "post": candidate,
                "post_summary": post_summary(candidate),
                "score": score,
                "reasons": reasons,
                "computed_at": now,
            }
        )

    candidates.sort(key=lambda item: (-item["score"], -item["post"].created_at.timestamp(), -item["post"].id))
    return candidates[:limit]
