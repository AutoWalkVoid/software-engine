"""分页解析与切页（契约 2.5：page 默认 1，page_size 默认 20、范围 1～100）。"""
import math

from common.exceptions import ApiError


def parse_page_params(params) -> tuple[int, int]:
    raw_page = params.get("page", "1")
    raw_size = params.get("page_size", "20")

    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        raise ApiError(400, "VALIDATION_ERROR", "请检查填写内容", {"page": ["页码必须为正整数"]})
    try:
        page_size = int(raw_size)
    except (TypeError, ValueError):
        raise ApiError(400, "VALIDATION_ERROR", "请检查填写内容", {"page_size": ["每页条数必须为正整数"]})

    if page < 1:
        raise ApiError(400, "VALIDATION_ERROR", "请检查填写内容", {"page": ["页码必须大于 0"]})
    if page_size < 1 or page_size > 100:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "请检查填写内容",
            {"page_size": ["每页条数必须在 1～100 之间"]},
        )
    return page, page_size


def paginate(queryset, page: int, page_size: int):
    total = queryset.count()
    total_pages = math.ceil(total / page_size) if total else 0
    offset = (page - 1) * page_size
    items = list(queryset[offset: offset + page_size])
    return items, {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
