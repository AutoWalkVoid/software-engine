"""B 子系统（信息发布与浏览）Django 项目配置。

本文件只服务 B 模块 v0 原型：
- 数据库为 SQLite，表结构即契约 3.4/3.5/3.6 的落库形态；
- 登录身份不落库（用户表属 A），一律通过 A_IDENTITY_URL 向 A 校验；
- 图片不进静态目录，统一保存在 PRIVATE_MEDIA_ROOT，经 content 接口读取。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("B_SECRET_KEY", "dev-only-secret-key-not-for-production")
DEBUG = os.environ.get("B_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "catalog",
    "posts",
    "workflow",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": False,
        "OPTIONS": {"context_processors": []},
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "var" / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = None

# 图片私有存储目录：不挂在静态 URL 下，只能经 /api/v1/post-images/{id}/content 读取
PRIVATE_MEDIA_ROOT = BASE_DIR / "var" / "media"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024 + 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# 契约要求路径不带结尾斜杠
APPEND_SLASH = False

# ------- 跨子系统集成（A 用户、C 认领）-------
# A 的身份校验接口，建议指向 A 的 GET /api/v1/users/me；未配置时所有登录请求一律 401。
A_IDENTITY_URL = os.environ.get("A_IDENTITY_URL", "")
A_IDENTITY_TIMEOUT = float(os.environ.get("A_IDENTITY_TIMEOUT", "3"))
# C 的认领服务基地址；未配置时撤回不调用 C（仅本地开发，见 README「与契约的差异」）
C_BASE_URL = os.environ.get("C_BASE_URL", "").rstrip("/")
C_TIMEOUT = float(os.environ.get("C_TIMEOUT", "3"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["integration.auth.BearerAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "DEFAULT_PAGINATION_CLASS": None,
    "DATETIME_FORMAT": "iso-8601",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("B_LOG_LEVEL", "INFO")},
}
