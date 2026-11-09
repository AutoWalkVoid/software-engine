from django.urls import include, path, re_path

from common.views import api_not_found

urlpatterns = [
    path("api/v1/", include("catalog.urls")),
    path("api/v1/", include("posts.urls")),
    # 兜底：/api/v1 下未匹配的路径也返回契约规定的 JSON 404，而不是 HTML 调试页
    re_path(r"^api/v1/.*$", api_not_found),
]
