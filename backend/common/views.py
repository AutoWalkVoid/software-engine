"""未匹配到任何 API 路由时的 JSON 404。

Django 默认对未匹配路径返回 HTML 404（DEBUG=True 时是调试页），而契约 2.4 要求
所有接口失败都走 {code,message,data,errors}。这个兜底视图只挂在 /api/v1/ 下。
"""
from django.http import JsonResponse


def api_not_found(request, *args, **kwargs):
    return JsonResponse(
        {
            "code": "NOT_FOUND",
            "message": "接口或资源不存在",
            "data": None,
            "errors": {},
        },
        status=404,
        json_dumps_params={"ensure_ascii": False},
    )
