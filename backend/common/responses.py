"""统一成功响应包装：{code, message, data}。

契约见《共同字段与接口约定-03》2.3。所有 JSON 接口（图片二进制接口除外）
都必须经过 ok() 或异常处理器，保证前端只解析一种结构。
"""
from rest_framework.response import Response


def ok(data=None, message: str = "操作成功", status: int = 200, headers=None) -> Response:
    return Response(
        {"code": "OK", "message": message, "data": data},
        status=status,
        headers=headers,
    )
