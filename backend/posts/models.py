"""信息与图片模型（契约 3.5 / 3.6）。

Post 是 B 子系统的核心表；A 的「我的发布」直接查询本表（按 publisher_id 过滤）。
PostImage 的二进制不进静态目录，只经 /api/v1/post-images/{id}/content 读取。
"""
import os
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import models


class PrivateImageStorage(FileSystemStorage):
    """私有图片存储：目录不在 STATIC_URL 下，只能通过视图鉴权后读取。

    位置在访问时从 settings 读取，便于测试用 override_settings 指向临时目录。
    """

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(str(settings.PRIVATE_MEDIA_ROOT))


private_image_storage = PrivateImageStorage()


class Post(models.Model):
    POST_TYPE_LOST = "lost"
    POST_TYPE_FOUND = "found"
    POST_TYPE_CHOICES = [(POST_TYPE_LOST, "失物"), (POST_TYPE_FOUND, "招领")]

    STATUS_OPEN = "open"
    STATUS_IN_HANDOVER = "in_handover"
    STATUS_COMPLETED = "completed"
    STATUS_WITHDRAWN = "withdrawn"
    STATUS_CHOICES = [
        (STATUS_OPEN, "进行中"),
        (STATUS_IN_HANDOVER, "交接中"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_WITHDRAWN, "已撤回"),
    ]
    #: 公开列表默认展示的状态集合（契约 3.5 / 5.3）
    PUBLIC_STATUSES = (STATUS_OPEN, STATUS_IN_HANDOVER)

    publisher_id = models.CharField(max_length=64, db_index=True)
    # 发布者在发布时从 A 的身份响应里取得的 UserSummary 快照；
    # A 提供实时批量摘要接口后由 integration.users 覆盖，见 README。
    publisher_nickname = models.CharField(max_length=30, blank=True, default="")
    publisher_is_campus_verified = models.BooleanField(default=False)
    publisher_verification_mode = models.CharField(max_length=10, blank=True, default="")

    post_type = models.CharField(max_length=10, choices=POST_TYPE_CHOICES)
    title = models.CharField(max_length=60)
    description = models.CharField(max_length=2000)
    category = models.ForeignKey("catalog.Category", on_delete=models.PROTECT, related_name="posts")
    location = models.ForeignKey("catalog.Location", on_delete=models.PROTECT, related_name="posts")
    # campus 由 location 推导，不接受客户端提交
    campus = models.ForeignKey("catalog.Campus", on_delete=models.PROTECT, related_name="posts")
    location_detail = models.CharField(max_length=100, blank=True, default="")
    occurred_at = models.DateTimeField()
    handover_note = models.CharField(max_length=200, null=True, blank=True, default=None)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    # 幂等键：同一发布者 + 同一 request_id 只建一条；空串表示未提供
    request_id = models.CharField(max_length=64, blank=True, default="")

    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts_post"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["publisher_id", "request_id"],
                condition=~models.Q(request_id=""),
                name="uniq_post_publisher_request",
            )
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="idx_post_status_created"),
            models.Index(fields=["category", "location"], name="idx_post_cat_loc"),
        ]

    def __str__(self):
        return f"Post#{self.pk} {self.post_type} {self.title}"

    @property
    def is_public(self) -> bool:
        return self.status != self.STATUS_WITHDRAWN


class PostImage(models.Model):
    owner_id = models.CharField(max_length=64, db_index=True)
    post = models.ForeignKey(
        Post, null=True, blank=True, on_delete=models.SET_NULL, related_name="images"
    )
    file = models.FileField(storage=private_image_storage, upload_to="post-images/", max_length=255)
    mime_type = models.CharField(max_length=32)
    size_bytes = models.PositiveIntegerField()
    sort_order = models.PositiveIntegerField(default=0)
    alt_text = models.CharField(max_length=100)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts_postimage"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"PostImage#{self.pk} owner={self.owner_id}"

    def save_bytes(self, data: bytes, mime_type: str) -> None:
        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime_type]
        name = f"{uuid.uuid4().hex}.{ext}"
        self.file.save(name, ContentFile(data), save=False)
        self.mime_type = mime_type
        self.size_bytes = len(data)

    def delete_file(self) -> None:
        if self.file:
            self.file.delete(save=False)
