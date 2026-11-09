"""统一错误响应与业务异常。

契约 2.4：失败响应固定 {code, message, data: null, errors: {}}。
HTTP 状态与 code 的映射：
400 VALIDATION_ERROR / 401 UNAUTHENTICATED / 403 FORBIDDEN / 403 IDENTITY_REQUIRED /
404 NOT_FOUND / 409 STATE_CONFLICT|DUPLICATE_RESOURCE / 413 FILE_TOO_LARGE /
415 UNSUPPORTED_MEDIA_TYPE / 429 RATE_LIMITED / 500 INTERNAL_ERROR。
"""
import logging

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response

logger = logging.getLogger("b.api")


class ApiError(APIException):
    """带业务码的异常；由 api_exception_handler 统一转成错误信封。"""

    def __init__(self, status_code: int, code: str, message: str, errors=None, headers=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.errors = errors or {}
        self.headers = headers or {}
        super().__init__(detail=message)


def error_envelope(status_code: int, code: str, message: str, errors=None, headers=None) -> Response:
    return Response(
        {
            "code": code,
            "message": message,
            "data": None,
            "errors": errors or {},
        },
        status=status_code,
        headers=headers,
    )


def _flatten(detail):
    """把 DRF 的 ErrorDetail 树压平成 {字段: [中文/原始文案]}。"""
    if isinstance(detail, dict):
        result = {}
        for key, value in detail.items():
            result[str(key)] = _flatten(value)
        return result
    if isinstance(detail, (list, tuple)):
        out = []
        for item in detail:
            if isinstance(item, (dict, list, tuple)):
                out.extend(_flatten(item) if isinstance(item, list) else [str(item)])
            else:
                out.append(str(item))
        return out
    return [str(detail)]


_STATUS_MAP = {
    400: ("VALIDATION_ERROR", "请检查填写内容"),
    401: ("UNAUTHENTICATED", "未登录或登录凭证无效"),
    403: ("FORBIDDEN", "没有操作权限"),
    404: ("NOT_FOUND", "资源不存在"),
    405: ("METHOD_NOT_ALLOWED", "请求方法不被允许"),
    413: ("FILE_TOO_LARGE", "图片超过大小限制"),
    415: ("UNSUPPORTED_MEDIA_TYPE", "请求内容类型或图片格式不支持"),
    429: ("RATE_LIMITED", "请求过于频繁，请稍后再试"),
}


def api_exception_handler(exc, context):
    # 延迟导入：DRF 初始化时会在 rest_framework.views 尚未就绪的情况下导入
    # integration.auth → common.exceptions，模块级导入会形成循环依赖。
    from rest_framework.views import exception_handler as drf_exception_handler

    if isinstance(exc, ApiError):
        return error_envelope(exc.status_code, exc.code, exc.message, exc.errors, exc.headers)

    if isinstance(exc, ValidationError):
        return error_envelope(
            status.HTTP_400_BAD_REQUEST,
            "VALIDATION_ERROR",
            "请检查填写内容",
            _flatten(exc.detail),
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("未处理的异常: %s", exc)
        return error_envelope(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "服务端错误",
        )

    code, message = _STATUS_MAP.get(response.status_code, ("VALIDATION_ERROR", "请求不合法"))
    errors = {}
    if response.data is not None and response.status_code >= 400 and "detail" not in str(response.data):
        errors = _flatten(response.data)
    return error_envelope(response.status_code, code, message, errors)
