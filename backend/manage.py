#!/usr/bin/env python
"""Django 管理入口（B 子系统 v0 原型）。"""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "无法导入 Django，请确认已安装依赖并在 backend 目录下使用 .venv 运行。"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
