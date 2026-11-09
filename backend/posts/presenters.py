"""响应结构组装：严格按契约 3.9 的 PostSummary / PostDetail / PostImageView。"""
from rest_framework import serializers as drf_serializers

_DATETIME = drf_serializers.DateTimeField()


def iso(dt):
    return None if dt is None else _DATETIME.to_representation(dt)


def image_view(image) -> dict:
    return {
        "id": str(image.id),
        "url": f"/api/v1/post-images/{image.id}/content",
        "mime_type": image.mime_type,
        "size_bytes": image.size_bytes,
        "sort_order": image.sort_order,
        "alt_text": image.alt_text,
        "is_public": image.is_public,
    }


def publisher_summary(post) -> dict:
    """UserSummary 的 B 侧快照。

    昵称与认证状态来自发布时 A 返回的 UserSelf；A 提供实时批量摘要接口后，
    由 integration.users.get_user_summaries 覆盖这一函数即可。
    """
    return {
        "id": post.publisher_id,
        "nickname": post.publisher_nickname,
        "is_campus_verified": post.publisher_is_campus_verified,
        "verification_mode": post.publisher_verification_mode or None,
    }


def _ordered_images(post):
    return list(post.images.all())


def post_summary(post, images=None) -> dict:
    if images is None:
        images = _ordered_images(post)
    cover = image_view(images[0]) if images else None
    return {
        "id": str(post.id),
        "post_type": post.post_type,
        "title": post.title,
        "category": {"id": post.category_id, "name": post.category.name},
        "campus": {"id": post.campus_id, "name": post.campus.name},
        "location": {"id": post.location_id, "name": post.location.name},
        "occurred_at": iso(post.occurred_at),
        "status": post.status,
        "cover_image": cover,
        "publisher": publisher_summary(post),
        "created_at": iso(post.created_at),
        "updated_at": iso(post.updated_at),
    }


def post_detail(post, images=None) -> dict:
    if images is None:
        images = _ordered_images(post)
    data = post_summary(post, images)
    data.update(
        {
            "description": post.description,
            "location_detail": post.location_detail,
            "handover_note": post.handover_note,
            "images": [image_view(image) for image in images],
            "completed_at": iso(post.completed_at),
        }
    )
    return data
