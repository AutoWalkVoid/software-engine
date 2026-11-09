"""种子数据：1 个校区、6 个分类、5 个地点（契约 3.4 / FR-01）。

幂等：使用 update_or_create，重复执行不会产生重复行；已被使用的字典项不删除、
不重新解释（模型外键为 PROTECT）。
"""
from django.db import migrations

CAMPUSES = [("campus_main", "主校区")]

CATEGORIES = [
    ("cat_document", "证件", 10),
    ("cat_electronics", "电子产品", 20),
    ("cat_keys", "钥匙", 30),
    ("cat_books", "书籍", 40),
    ("cat_clothing", "衣物", 50),
    ("cat_other", "其他", 60),
]

LOCATIONS = [
    ("loc_library", "图书馆", 10),
    ("loc_teaching_building", "教学楼", 20),
    ("loc_canteen", "食堂", 30),
    ("loc_playground", "操场", 40),
    ("loc_dormitory", "宿舍楼", 50),
]


def seed(apps, schema_editor):
    Campus = apps.get_model("catalog", "Campus")
    Category = apps.get_model("catalog", "Category")
    Location = apps.get_model("catalog", "Location")

    for campus_id, name in CAMPUSES:
        Campus.objects.update_or_create(id=campus_id, defaults={"name": name})
    for category_id, name, sort_order in CATEGORIES:
        Category.objects.update_or_create(
            id=category_id, defaults={"name": name, "sort_order": sort_order}
        )
    for location_id, name, sort_order in LOCATIONS:
        Location.objects.update_or_create(
            id=location_id,
            defaults={"campus_id": CAMPUSES[0][0], "name": name, "sort_order": sort_order},
        )


def unseed(apps, schema_editor):
    Location = apps.get_model("catalog", "Location")
    Category = apps.get_model("catalog", "Category")
    Campus = apps.get_model("catalog", "Campus")
    Location.objects.filter(id__in=[item[0] for item in LOCATIONS]).delete()
    Category.objects.filter(id__in=[item[0] for item in CATEGORIES]).delete()
    Campus.objects.filter(id__in=[item[0] for item in CAMPUSES]).delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
