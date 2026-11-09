from datetime import timedelta

from django.utils import timezone

from posts.models import Post
from tests.support import BTestCase


class PublishTests(BTestCase):
    def test_publish_requires_login(self):
        response = self.client.post("/api/v1/posts", self.post_payload(), format="json")
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["code"], "UNAUTHENTICATED")
        self.assertIsNone(body["data"])
        self.assertEqual(Post.objects.count(), 0)

    def test_publish_lost_success_sets_server_side_fields(self):
        self.login()
        response = self.client.post("/api/v1/posts", self.post_payload(), format="json")
        self.assertEqual(response.status_code, 201, response.json())
        data = response.json()["data"]
        self.assertEqual(data["status"], "open")
        self.assertEqual(data["publisher"]["id"], "1001")
        self.assertEqual(data["publisher"]["nickname"], "小林")
        self.assertEqual(data["campus"]["id"], "campus_main")  # 由地点推导
        self.assertIsNone(data["handover_note"])
        self.assertIsNone(data["completed_at"])
        self.assertEqual(data["images"], [])
        self.assertTrue(data["id"].isdigit())

        post = Post.objects.get(pk=int(data["id"]))
        self.assertEqual(post.publisher_id, "1001")
        self.assertEqual(post.status, "open")

    def test_publish_rejects_client_supplied_publisher_id(self):
        self.login()
        payload = self.post_payload(publisher_id="1002")
        response = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["code"], "VALIDATION_ERROR")
        self.assertIn("publisher_id", body["errors"])
        self.assertEqual(Post.objects.count(), 0)

    def test_publish_found_requires_campus_verification(self):
        self.login("tok-bob")  # 未完成校园身份绑定
        payload = self.post_payload(
            post_type="found",
            title="拾到一串钥匙",
            handover_note="暂由本人保管，核实后在校内交接。",
        )
        response = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body["code"], "IDENTITY_REQUIRED")
        self.assertIn("失物招领处", body["message"])
        self.assertEqual(Post.objects.count(), 0)

    def test_publish_found_ok_when_verified(self):
        self.login()
        payload = self.post_payload(
            post_type="found",
            title="拾到一串钥匙",
            category_id="cat_keys",
            handover_note="暂由本人保管，核实特征后在校内约定地点交接。",
        )
        response = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["data"]["status"], "open")
        self.assertEqual(response.json()["data"]["handover_note"], "暂由本人保管，核实特征后在校内约定地点交接。")

    def test_found_without_handover_note_is_400(self):
        self.login()
        payload = self.post_payload(post_type="found", title="拾到一串钥匙")
        payload.pop("handover_note", None)
        response = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("handover_note", response.json()["errors"])

    def test_lost_with_handover_note_is_400(self):
        self.login()
        payload = self.post_payload(handover_note="不该出现")
        response = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("handover_note", response.json()["errors"])

    def test_field_bounds(self):
        self.login()
        cases = [
            ({"title": "钱"}, "title"),
            ({"title": "标" * 61}, "title"),
            ({"description": "太短了"}, "description"),
            ({"description": "字" * 2001}, "description"),
            ({"occurred_at": (timezone.now() + timedelta(minutes=5)).isoformat()}, "occurred_at"),
            ({"category_id": "cat_nope"}, "category_id"),
            ({"location_id": "loc_nope"}, "location_id"),
            ({"location_detail": "地" * 101}, "location_detail"),
        ]
        for overrides, field in cases:
            with self.subTest(field=field, overrides=overrides):
                response = self.client.post("/api/v1/posts", self.post_payload(**overrides), format="json")
                self.assertEqual(response.status_code, 400)
                body = response.json()
                self.assertEqual(body["code"], "VALIDATION_ERROR")
                self.assertIn(field, body["errors"])
        self.assertEqual(Post.objects.count(), 0)

    def test_unknown_field_is_400(self):
        self.login()
        payload = self.post_payload(status="completed")
        response = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.json()["errors"])

    def test_request_id_is_idempotent(self):
        self.login()
        payload = self.post_payload(request_id="req-0001")
        first = self.client.post("/api/v1/posts", payload, format="json")
        second = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200, second.json())
        self.assertEqual(first.json()["data"]["id"], second.json()["data"]["id"])
        self.assertEqual(Post.objects.count(), 1)

    def test_duplicate_image_ids_are_400(self):
        self.login()
        image = self.create_image()
        payload = self.post_payload(image_ids=[str(image.id), str(image.id)])
        response = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("image_ids", response.json()["errors"])

    def test_cannot_bind_others_image(self):
        self.login()
        image = self.create_image(owner_id="1002")
        payload = self.post_payload(image_ids=[str(image.id)])
        response = self.client.post("/api/v1/posts", payload, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Post.objects.count(), 0)
        image.refresh_from_db()
        self.assertIsNone(image.post_id)
