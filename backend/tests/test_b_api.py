"""B 子系统接口的端到端测试（不依赖 C 的认领模块）。

用 Django 的 ``TestCase`` 而不是 pytest，保证 ``manage.py test`` 一条命令就能跑，
不需要额外安装 pytest-django。
"""

from __future__ import annotations

import base64
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from identity.models import DemoUser
from identity.services import issue_token

API = "/api/v1"
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
HAPPENED = (timezone.now() - timedelta(days=1)).isoformat()


def post_payload(**overrides):
    data = {
        "post_type": "found",
        "title": "图书馆拾到黑色钱包",
        "description": "在图书馆一楼自习区拾到一只黑色钱包，内有校园卡，请说明特征。",
        "category_id": "daily",
        "location_id": "library",
        "occurred_at": HAPPENED,
        "handover_note": "请到图书馆前台找我，核对身份后归还。",
    }
    data.update(overrides)
    return data


def lost_payload(**overrides):
    data = {
        "post_type": "lost",
        "title": "丢失银色钥匙扣",
        "description": "在体育馆更衣室丢失一串钥匙，共三把，其中一把是自行车钥匙。",
        "category_id": "keys",
        "location_id": "gym",
        "occurred_at": HAPPENED,
    }
    data.update(overrides)
    return data


class BApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = cls.client_for("alice")       # 已校园认证
        cls.bob = cls.client_for("bob")           # 已校园认证
        cls.outsider = cls.client_for("outsider")  # 未认证
        cls.anon = APIClient()

    @staticmethod
    def client_for(actor):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_token(actor)['access_token']}")
        return client

    def publish(self, client=None, payload=None):
        return (client or self.alice).post(f"{API}/posts", payload or post_payload(), format="json")

    # ---------------------------------------------------------------- 字典与健康检查
    def test_meta_lists(self):
        campuses = self.anon.get(f"{API}/meta/campuses")
        self.assertEqual(campuses.status_code, 200)
        self.assertEqual([row["id"] for row in campuses.json()["data"]], ["main"])

        categories = self.anon.get(f"{API}/meta/categories")
        self.assertEqual(
            [row["id"] for row in categories.json()["data"]][:3], ["keys", "daily", "books"]
        )

        locations = self.anon.get(f"{API}/meta/locations", {"campus_id": "main"})
        self.assertEqual(locations.status_code, 200)
        self.assertGreaterEqual(len(locations.json()["data"]), 4)
        self.assertEqual(
            self.anon.get(f"{API}/meta/locations", {"campus_id": "nope"}).status_code, 400
        )

    def test_health(self):
        self.assertEqual(self.anon.get(f"{API}/health").status_code, 200)

    # ---------------------------------------------------------------- 发布
    def test_publish_requires_login(self):
        self.assertEqual(self.anon.post(f"{API}/posts", post_payload(), format="json").status_code, 401)

    def test_found_requires_campus_verification(self):
        response = self.publish(self.outsider)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "IDENTITY_REQUIRED")

    def test_publish_validation_rules(self):
        for overrides in (
            {"description": "太短"},
            {"occurred_at": (timezone.now() + timedelta(days=1)).isoformat()},
            {"handover_note": None},
            {"image_ids": ["1", "1"]},
        ):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.publish(payload=post_payload(**overrides)).status_code, 400)

        with self.subTest("失物不能带交接说明"):
            self.assertEqual(
                self.publish(payload=lost_payload(handover_note="不该有")).status_code, 400
            )

    def test_publish_and_read_detail(self):
        response = self.publish()
        self.assertEqual(response.status_code, 201)
        body = response.json()["data"]
        self.assertEqual(len(body["id"]), 36)  # UUID 字符串主键
        self.assertIsNone(body["cover_image"])
        self.assertEqual(body["status"], "open")

        detail = self.anon.get(f"{API}/posts/{body['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["title"], "图书馆拾到黑色钱包")

    def test_request_id_is_idempotent(self):
        payload = post_payload(request_id="req-0001")
        first = self.publish(payload=payload)
        second = self.publish(payload=payload)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["data"]["id"], second.json()["data"]["id"])

    # ---------------------------------------------------------------- 列表与检索
    def test_list_default_visibility(self):
        completed = self.publish(payload=lost_payload())
        self.alice.post(
            f"{API}/posts/{completed.json()['data']['id']}/resolve",
            {"resolve_note": "已经找回并归还失主"},
            format="json",
        )
        withdrawn = self.publish()
        self.alice.post(f"{API}/posts/{withdrawn.json()['data']['id']}/withdraw", {}, format="json")
        self.publish()  # 一条正常的 found

        listed = self.anon.get(f"{API}/posts").json()["data"]
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["items"][0]["status"], "open")

        only_completed = self.anon.get(f"{API}/posts", {"status": "completed"}).json()["data"]
        self.assertEqual(only_completed["total"], 1)
        self.assertEqual(
            self.anon.get(f"{API}/posts", {"status": "withdrawn"}).status_code, 400
        )

    def test_keyword_is_literal_and_case_sensitive(self):
        self.publish()
        self.publish(payload=post_payload(title="BLACK WALLET", description="A black wallet found in the library hall."))
        self.assertEqual(self.anon.get(f"{API}/posts", {"keyword": "钱包"}).json()["data"]["total"], 1)
        self.assertEqual(self.anon.get(f"{API}/posts", {"keyword": "wallet"}).json()["data"]["total"], 1)
        self.assertEqual(self.anon.get(f"{API}/posts", {"keyword": "Wallet"}).json()["data"]["total"], 0)
        self.assertEqual(self.anon.get(f"{API}/posts", {"keyword": "%"}).json()["data"]["total"], 0)
        self.assertEqual(self.anon.get(f"{API}/posts", {"keyword": "_"}).json()["data"]["total"], 0)

    def test_filters_and_sorting(self):
        self.publish()
        self.publish(payload=lost_payload())
        self.assertEqual(self.anon.get(f"{API}/posts", {"post_type": "lost"}).json()["data"]["total"], 1)
        self.assertEqual(self.anon.get(f"{API}/posts", {"campus_id": "main"}).json()["data"]["total"], 2)
        self.assertEqual(self.anon.get(f"{API}/posts", {"campus_id": "nope"}).status_code, 400)
        self.assertEqual(self.anon.get(f"{API}/posts", {"sort": "bad"}).status_code, 400)
        self.assertEqual(self.anon.get(f"{API}/posts", {"sort": "occurred_latest"}).status_code, 200)

    def test_pagination_bounds(self):
        self.publish()
        data = self.anon.get(f"{API}/posts", {"page": 99}).json()["data"]
        self.assertEqual(data["items"], [])
        self.assertEqual(data["total"], 1)
        self.assertEqual(self.anon.get(f"{API}/posts", {"page_size": 101}).status_code, 400)

    # ---------------------------------------------------------------- 编辑
    def test_edit_permissions_and_state(self):
        post_id = self.publish().json()["data"]["id"]
        edited = self.alice.patch(f"{API}/posts/{post_id}", {"title": "钱包（已确认）"}, format="json")
        self.assertEqual(edited.status_code, 200)
        self.assertNotEqual(edited.json()["data"]["updated_at"], edited.json()["data"]["created_at"])

        self.assertEqual(
            self.bob.patch(f"{API}/posts/{post_id}", {"title": "越权改名"}, format="json").status_code,
            403,
        )
        self.assertEqual(
            self.alice.patch(f"{API}/posts/{post_id}", {"post_type": "lost"}, format="json").status_code,
            400,
        )
        self.assertEqual(
            self.alice.patch(f"{API}/posts/{post_id}", {}, format="json").status_code, 400
        )

    # ---------------------------------------------------------------- 生命周期
    def test_withdraw_and_restore(self):
        post_id = self.publish().json()["data"]["id"]
        self.assertEqual(
            self.alice.post(f"{API}/posts/{post_id}/withdraw", {}, format="json").status_code, 200
        )
        self.assertEqual(self.anon.get(f"{API}/posts/{post_id}").status_code, 404)
        self.assertEqual(self.anon.get(f"{API}/posts").json()["data"]["total"], 0)
        self.assertEqual(
            self.alice.post(f"{API}/posts/{post_id}/restore", {}, format="json").json()["data"]["status"],
            "open",
        )

    def test_resolve_and_reopen(self):
        post_id = self.publish(payload=lost_payload()).json()["data"]["id"]
        self.assertEqual(
            self.alice.post(
                f"{API}/posts/{post_id}/resolve", {"resolve_note": "已经找回并归还失主"}, format="json"
            ).json()["data"]["status"],
            "completed",
        )
        self.assertEqual(
            self.alice.post(f"{API}/posts/{post_id}/reopen", {}, format="json").json()["data"]["status"],
            "open",
        )
        # 招领不能自行办结
        found_id = self.publish().json()["data"]["id"]
        self.assertEqual(
            self.alice.post(
                f"{API}/posts/{found_id}/resolve", {"resolve_note": "招领不能自行办结"}, format="json"
            ).status_code,
            409,
        )

    def test_repeated_state_action_conflicts(self):
        post_id = self.publish().json()["data"]["id"]
        self.alice.post(f"{API}/posts/{post_id}/withdraw", {}, format="json")
        again = self.alice.post(f"{API}/posts/{post_id}/withdraw", {}, format="json")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["code"], "STATE_CONFLICT")

    # ---------------------------------------------------------------- 图片
    def test_image_upload_and_visibility(self):
        upload = SimpleUploadedFile("wallet.png", PNG_1PX, content_type="image/png")
        response = self.alice.post(
            f"{API}/post-images",
            {"file": upload, "alt_text": "钱包正面特写", "is_public": "true"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        image = response.json()["data"]
        self.assertIn("is_public", image)

        post_id = self.publish().json()["data"]["id"]
        bound = self.alice.patch(f"{API}/posts/{post_id}", {"image_ids": [image["id"]]}, format="json")
        self.assertEqual(bound.status_code, 200)
        self.assertEqual(bound.json()["data"]["cover_image"]["id"], image["id"])
        self.assertEqual(self.anon.get(f"{API}/post-images/{image['id']}/content").status_code, 200)

        rejected = self.alice.post(
            f"{API}/post-images",
            {"file": SimpleUploadedFile("x.png", PNG_1PX, content_type="image/png"), "alt_text": "image"},
            format="multipart",
        )
        self.assertEqual(rejected.status_code, 400)

    # ---------------------------------------------------------------- 发布者降级
    def test_missing_publisher_falls_back(self):
        self.publish()
        DemoUser.objects.filter(pk="alice").delete()
        listed = self.anon.get(f"{API}/posts")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            {item["publisher"]["nickname"] for item in listed.json()["data"]["items"]},
            {"已注销用户"},
        )
