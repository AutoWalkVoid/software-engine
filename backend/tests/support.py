"""测试公共设施：A 的身份校验用 mock 注入，媒体目录指向 backend/var/test-media。"""
import base64
import shutil
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from integration.auth import InvalidToken
from posts.models import Post, PostImage

# 1x1 透明 PNG
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

IDENTITIES = {
    "tok-alice": {
        "id": "1001",
        "nickname": "小林",
        "is_campus_verified": True,
        "verification_mode": "demo",
    },
    "tok-bob": {
        "id": "1002",
        "nickname": "小周",
        "is_campus_verified": False,
        "verification_mode": "",
    },
    "tok-carol": {
        "id": "1003",
        "nickname": "小陈",
        "is_campus_verified": True,
        "verification_mode": "demo",
    },
}


def fake_fetch_identity(token: str) -> dict:
    if token not in IDENTITIES:
        raise InvalidToken(f"unknown token: {token}")
    return dict(IDENTITIES[token])


class BTestCase(APITestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.media_root = Path(settings.BASE_DIR) / "var" / "test-media"
        if cls.media_root.exists():
            shutil.rmtree(cls.media_root, ignore_errors=True)
        cls.media_root.mkdir(parents=True, exist_ok=True)
        cls._settings_override = override_settings(PRIVATE_MEDIA_ROOT=str(cls.media_root))
        cls._settings_override.enable()
        super().setUpClass()
        cls._auth_patch = patch("integration.auth.fetch_identity", side_effect=fake_fetch_identity)
        cls._auth_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._auth_patch.stop()
        cls._settings_override.disable()
        super().tearDownClass()
        shutil.rmtree(cls.media_root, ignore_errors=True)

    # ---------------- 身份
    def login(self, token: str = "tok-alice"):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def logout(self):
        self.client.credentials()

    # ---------------- 数据
    def post_payload(self, **overrides) -> dict:
        payload = {
            "post_type": "lost",
            "title": "丢失的黑色钱包",
            "category_id": "cat_other",
            "description": "昨晚在图书馆二楼丢失，黑色皮质，内有校园卡。",
            "location_id": "loc_library",
            "location_detail": "二楼公共座位",
            "occurred_at": (timezone.now() - timedelta(hours=2)).isoformat(),
            "image_ids": [],
            "request_id": "",
        }
        payload.update(overrides)
        return payload

    def create_post(self, publisher_id="1001", post_type="lost", status="open", **overrides) -> Post:
        now = timezone.now()
        values = {
            "publisher_id": publisher_id,
            "publisher_nickname": "小林" if publisher_id == "1001" else "小周",
            "publisher_is_campus_verified": publisher_id == "1001",
            "publisher_verification_mode": "demo",
            "post_type": post_type,
            "title": "丢失的黑色钱包" if post_type == "lost" else "拾到一串钥匙",
            "description": "在图书馆二楼附近丢失，黑色皮质，内有校园卡与少量现金。",
            "category_id": "cat_other",
            "location_id": "loc_library",
            "campus_id": "campus_main",
            "location_detail": "二楼公共座位",
            "occurred_at": now - timedelta(hours=2),
            "handover_note": None
            if post_type == "lost"
            else "暂由本人保管，核实特征后在校内约定地点交接。",
            "status": status,
        }
        created_at = overrides.pop("created_at", None)
        values.update(overrides)
        post = Post.objects.create(**values)
        if created_at is not None:
            # auto_now_add 会覆盖传入值，需要建完再改
            Post.objects.filter(pk=post.pk).update(created_at=created_at)
            post.refresh_from_db()
        return post

    def create_image(self, owner_id="1001", post=None, alt_text="白色按键的蓝牙耳机", is_public=True):
        image = PostImage(owner_id=owner_id, post=post, alt_text=alt_text, is_public=is_public)
        image.sort_order = 0 if post is None else (post.images.count())
        image.save_bytes(PNG_BYTES, "image/png")
        image.save()
        return image
