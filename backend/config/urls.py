"""根路由：本仓库只提供 B 子系统的 API 与健康检查。

前端原型（``frontend/``）是独立的 Vite 工程，开发时由 Vite 自己起服务并通过代理访问
``/api/v1``，因此这里不挂 Django 静态页面路由，也不包含 C 的认领接口。
"""

from __future__ import annotations

from django.urls import include, path, re_path
from django.views.generic import RedirectView

from common.views import api_not_found, health

urlpatterns = [
    path("health", health, name="health"),
    # 契约 5.5：所有接口都带 /api/v1 前缀，/health 同理
    path("api/v1/health", health, name="health-api"),
    path("api/v1/", include("identity.urls")),
    path("api/v1/", include("users.urls")),
    path("api/v1/", include("catalog.urls")),
    path("api/v1/", include("posts.urls")),
    path("", RedirectView.as_view(url="/api/v1/health", permanent=False), name="root"),
    re_path(r"^.*$", api_not_found, name="not-found"),
]

handler404 = "common.errors.handler404"
handler500 = "common.errors.handler500"
