"""登录身份：B 不建用户表，只向 A 校验令牌（契约 2.2 / 7.3）。

- 读取 `Authorization: Bearer <token>`；
- 调用 A_IDENTITY_URL（建议指向 A 的 GET /api/v1/users/me），拿到 user_id 与 campus_verified；
- A 不可达或返回异常时一律 401，并写日志说明，绝不回退成固定假用户。
"""
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from common.exceptions import ApiError

logger = logging.getLogger("b.auth")


class IdentityUnavailable(Exception):
    """A 的校验接口不可用（网络错误、5xx、配置缺失）。"""


class InvalidToken(Exception):
    """A 明确判定令牌无效（401/403）。"""


@dataclass(frozen=True)
class Actor:
    """最小登录身份；字段与契约 7.3 的 require_user 返回一致。"""

    user_id: str
    campus_verified: bool = False
    nickname: str = ""
    verification_mode: str = ""

    is_authenticated = True
    is_anonymous = False

    @property
    def pk(self) -> str:
        return self.user_id

    @property
    def username(self) -> str:
        return self.user_id

    def __str__(self):
        return self.user_id


def fetch_identity(token: str) -> dict:
    """真实调用 A 的校验接口，返回 {id, nickname, is_campus_verified, verification_mode}。

    测试通过 mock 本函数注入身份；生产必须配置 A_IDENTITY_URL。
    """
    url = settings.A_IDENTITY_URL
    if not url:
        raise IdentityUnavailable("未配置 A_IDENTITY_URL，无法校验登录令牌")

    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.A_IDENTITY_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise InvalidToken(f"A 判定令牌无效: HTTP {exc.code}")
        raise IdentityUnavailable(f"A 校验接口返回 HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise IdentityUnavailable(f"无法连接 A 的校验接口: {exc}")

    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    user_id = data.get("id") or data.get("user_id")
    if not user_id:
        raise IdentityUnavailable("A 的校验响应缺少用户 ID")
    return {
        "id": str(user_id),
        "nickname": data.get("nickname") or "",
        "is_campus_verified": bool(data.get("is_campus_verified", False)),
        "verification_mode": data.get("verification_mode") or "",
    }


def verify_token(token: str) -> dict:
    try:
        return fetch_identity(token)
    except InvalidToken as exc:
        logger.warning("令牌校验失败: %s", exc)
        raise ApiError(401, "UNAUTHENTICATED", "登录凭证无效或已过期")
    except IdentityUnavailable as exc:
        logger.error("A 的身份服务不可用，按未登录处理: %s", exc)
        raise ApiError(401, "UNAUTHENTICATED", "暂时无法校验登录状态，请稍后再试")


class BearerAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = get_authorization_header(request)
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != b"bearer":
            raise ApiError(401, "UNAUTHENTICATED", "Authorization 头格式应为 Bearer <token>")
        token = parts[1].decode("utf-8", errors="ignore").strip()
        if not token:
            raise ApiError(401, "UNAUTHENTICATED", "登录凭证为空")
        identity = verify_token(token)
        actor = Actor(
            user_id=identity["id"],
            campus_verified=identity["is_campus_verified"],
            nickname=identity["nickname"],
            verification_mode=identity["verification_mode"],
        )
        return actor, token


def current_actor(request):
    """匿名访问返回 None，不抛异常；用于详情/图片的可见性判断。"""
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None


def require_actor(request) -> Actor:
    actor = current_actor(request)
    if actor is None:
        raise ApiError(401, "UNAUTHENTICATED", "请先登录")
    return actor


def require_campus_verified(actor: Actor) -> None:
    if not actor.campus_verified:
        raise ApiError(
            403,
            "IDENTITY_REQUIRED",
            "非校园用户不能发布招领，请将物品送至失物招领处",
        )
