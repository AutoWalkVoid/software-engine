"""A 的公开用户摘要（契约 3.9 UserSummary、7.3 get_user_summaries）。

B 不保存用户表。v0 在发布时把 A 返回的 UserSelf 快照写入 Post，读取时用
integration.users.get_user_summaries 统一出口；A 提供批量摘要接口后，只需把
本文件的实现换成一次 HTTP 调用，其它调用处不用改。
"""
import logging

from posts.models import Post

logger = logging.getLogger("b.users")


def get_user_summaries(user_ids) -> dict:
    """返回 {user_id: UserSummary}。

    v0 实现：从 Post 表的发布者快照里取（真实数据，不是编造）。
    对从未发布过信息的用户无法返回摘要——这是 B 侧不含用户表的已知限制，
    由 A 的批量摘要接口补齐。
    """
    ids = [str(uid) for uid in user_ids]
    if not ids:
        return {}

    summaries = {}
    posts = (
        Post.objects.filter(publisher_id__in=ids)
        .order_by("publisher_id", "-created_at")
        .values(
            "publisher_id",
            "publisher_nickname",
            "publisher_is_campus_verified",
            "publisher_verification_mode",
        )
    )
    for row in posts:
        uid = row["publisher_id"]
        if uid in summaries:
            continue
        summaries[uid] = {
            "id": uid,
            "nickname": row["publisher_nickname"],
            "is_campus_verified": row["publisher_is_campus_verified"],
            "verification_mode": row["publisher_verification_mode"] or None,
        }
    missing = [uid for uid in ids if uid not in summaries]
    if missing:
        logger.warning("A 未提供以下用户的摘要，B 侧也没有发布快照: %s", missing)
    return summaries


def get_user_summary(user_id: str) -> dict | None:
    return get_user_summaries([user_id]).get(str(user_id))
