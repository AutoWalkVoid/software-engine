"""基础数据字典：Campus / Category / Location（契约 3.4）。

字典使用固定初始化数据（种子迁移），第一版不提供管理页面。
ID 是对外字符串主键，三人共用同一份值，前端不能自造另一套枚举编号。
"""
from django.db import models


class Campus(models.Model):
    id = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=50)

    class Meta:
        db_table = "catalog_campus"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id}:{self.name}"


class Category(models.Model):
    id = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=50)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalog_category"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.id}:{self.name}"


class Location(models.Model):
    id = models.CharField(max_length=32, primary_key=True)
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, related_name="locations")
    name = models.CharField(max_length=50)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "catalog_location"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.id}:{self.name}"
