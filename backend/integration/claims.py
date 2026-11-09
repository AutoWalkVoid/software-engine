"""调用 C（失物认领）的内部接口（契约 5.4 / 7.3）。

B 在撤回信息时必须让 C 关闭该信息下所有 pending 申请，并且与撤回处在同一事务：
- 调用失败 → 抛异常 → 调用方事务回滚，信息不会变成 withdrawn；
- 未配置 C_BASE_URL 时（只跑 B 的 v0 环境）跳过远程调用并记录警告，
  这是契约 5.1「B 注记」允许的开发期开关，README 中有说明。
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

from common.exceptions import ApiError

logger = logging.getLogger("b.claims")


def _request_json(method: str, path: str, payload=None):
    url = f"{settings.C_BASE_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=settings.C_TIMEOUT) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:200]
        raise ApiError(
            503,
            "UPSTREAM_UNAVAILABLE",
            "认领服务拒绝或无法完成本次操作，信息状态未改变",
            {"c_service": [f"HTTP {exc.code}: {detail}"]},
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError(
            503,
            "UPSTREAM_UNAVAILABLE",
            "认领服务暂不可用，信息状态未改变",
            {"c_service": [str(exc)]},
        )
    try:
        return json.loads(body) if body else {}
    except ValueError:
        raise ApiError(
            503,
            "UPSTREAM_UNAVAILABLE",
            "认领服务返回了无法解析的内容",
            {"c_service": ["invalid json"]},
        )


def close_pending_claims(post_id, reason: str = "post_withdrawn", except_claim_id=None) -> dict:
    """关闭某条信息下所有 pending 认领申请（契约 7.3 的 C 函数）。"""
    if not settings.C_BASE_URL:
        logger.warning(
            "C_BASE_URL 未配置：撤回 post=%s 时未调用 close_pending_claims（仅限 B 单模块开发环境）",
            post_id,
        )
        return {"closed": 0, "skipped": True, "reason": "c_service_not_configured"}

    payload = {
        "post_id": str(post_id),
        "reason": reason,
        "except_claim_id": None if except_claim_id is None else str(except_claim_id),
    }
    result = _request_json("POST", "/api/v1/internal/claims/close-pending", payload)
    data = result.get("data", result) if isinstance(result, dict) else {}
    return data if isinstance(data, dict) else {"closed": 0}


def has_completed_claim(post_id) -> bool:
    """该信息是否存在 completed 认领记录（契约 7.3 的 C 函数）。

    未配置 C_BASE_URL 时 C 不可达，无法证明存在已完成认领；为不阻塞本地
    开发返回 False 并记录警告（README 已列为已知限制）。
    """
    if not settings.C_BASE_URL:
        logger.warning(
            "C_BASE_URL 未配置：无法查询 post=%s 的已完成认领记录，按 False 处理（仅限 B 单模块开发环境）",
            post_id,
        )
        return False

    result = _request_json("GET", f"/api/v1/internal/claims/has-completed?post_id={post_id}")
    data = result.get("data", result) if isinstance(result, dict) else {}
    if isinstance(data, bool):
        return data
    if isinstance(data, dict):
        return bool(data.get("has_completed_claim", data.get("has_completed")))
    return False
