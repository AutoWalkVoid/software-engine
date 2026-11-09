from datetime import timedelta

from django.utils import timezone

from tests.support import BTestCase


class EditTests(BTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post()

    def test_owner_can_edit_whitelisted_fields(self):
        self.login()
        response = self.client.patch(
            f"/api/v1/posts/{self.post.id}",
            {"title": "新的标题内容", "location_detail": "图书馆三楼"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()["data"]
        self.assertEqual(data["title"], "新的标题内容")
        self.assertEqual(data["location_detail"], "图书馆三楼")

    def test_post_type_status_publisher_are_rejected(self):
        self.login()
        for payload, field in (
            ({"post_type": "found"}, "post_type"),
            ({"status": "completed"}, "status"),
            ({"publisher_id": "1002"}, "publisher_id"),
            ({"completed_at": None}, "completed_at"),
            ({"campus_id": "campus_main"}, "campus_id"),
        ):
            with self.subTest(field=field):
                response = self.client.patch(
                    f"/api/v1/posts/{self.post.id}", payload, format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])
        self.post.refresh_from_db()
        self.assertEqual(self.post.post_type, "lost")
        self.assertEqual(self.post.publisher_id, "1001")

    def test_empty_patch_is_400(self):
        self.login()
        response = self.client.patch(f"/api/v1/posts/{self.post.id}", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.json()["errors"])

    def test_other_user_cannot_edit(self):
        self.login("tok-bob")
        response = self.client.patch(
            f"/api/v1/posts/{self.post.id}", {"title": "篡改标题内容"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_handover_state_blocks_edit(self):
        self.post.status = "in_handover"
        self.post.save(update_fields=["status"])
        self.login()
        response = self.client.patch(
            f"/api/v1/posts/{self.post.id}", {"title": "交接中改标题"}, format="json"
        )
        self.assertEqual(response.status_code, 409)

    def test_withdrawn_post_is_editable_by_owner(self):
        self.post.status = "withdrawn"
        self.post.save(update_fields=["status"])
        self.login()
        response = self.client.patch(
            f"/api/v1/posts/{self.post.id}", {"title": "撤回后修改标题"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "withdrawn")

    def test_edit_location_derives_campus(self):
        from catalog.models import Campus, Location

        Campus.objects.create(id="campus_b", name="分校区")
        Location.objects.create(id="loc_b", campus_id="campus_b", name="分校区食堂", sort_order=1)
        self.login()
        response = self.client.patch(
            f"/api/v1/posts/{self.post.id}", {"location_id": "loc_b"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["campus"]["id"], "campus_b")

    def test_edit_occurred_at_in_future_is_400(self):
        self.login()
        future = (timezone.now() + timedelta(hours=1)).isoformat()
        response = self.client.patch(
            f"/api/v1/posts/{self.post.id}", {"occurred_at": future}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("occurred_at", response.json()["errors"])

    def test_found_post_cannot_clear_handover_note(self):
        found = self.create_post(post_type="found")
        self.login()
        response = self.client.patch(
            f"/api/v1/posts/{found.id}", {"handover_note": ""}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("handover_note", response.json()["errors"])

    def test_image_ids_replace_and_reorder(self):
        first = self.create_image(owner_id="1001")
        second = self.create_image(owner_id="1001")
        self.login()

        response = self.client.patch(
            f"/api/v1/posts/{self.post.id}",
            {"image_ids": [str(second.id), str(first.id)]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([img["id"] for img in response.json()["data"]["images"]], [str(second.id), str(first.id)])
        self.assertEqual([img["sort_order"] for img in response.json()["data"]["images"]], [0, 1])

        cleared = self.client.patch(
            f"/api/v1/posts/{self.post.id}", {"image_ids": []}, format="json"
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["data"]["images"], [])
        first.refresh_from_db()
        self.assertIsNone(first.post_id)
