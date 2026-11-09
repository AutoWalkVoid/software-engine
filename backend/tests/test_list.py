from datetime import timedelta

from django.utils import timezone

from catalog.models import Location
from tests.support import BTestCase


class ListTests(BTestCase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.open_post = self.create_post(title="丢失的黑色钱包")
        self.handover_post = self.create_post(status="in_handover", title="交接中的钥匙")
        self.completed_post = self.create_post(status="completed", title="已完成的雨伞")
        self.withdrawn_post = self.create_post(status="withdrawn", title="已撤回的证件")

    def ids(self, response):
        return [item["id"] for item in response.json()["data"]["items"]]

    def test_default_statuses_are_open_and_in_handover(self):
        response = self.client.get("/api/v1/posts")
        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]
        self.assertEqual(items["total"], 2)
        self.assertNotIn(str(self.withdrawn_post.id), self.ids(response))
        self.assertNotIn(str(self.completed_post.id), self.ids(response))
        self.assertIn(str(self.open_post.id), self.ids(response))
        self.assertIn(str(self.handover_post.id), self.ids(response))

    def test_status_filter_completed_and_withdrawn_rejected(self):
        completed = self.client.get("/api/v1/posts", {"status": "completed"})
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(self.ids(completed), [str(self.completed_post.id)])

        withdrawn = self.client.get("/api/v1/posts", {"status": "withdrawn"})
        self.assertEqual(withdrawn.status_code, 400)
        self.assertIn("status", withdrawn.json()["errors"])

    def test_keyword_is_case_sensitive_literal(self):
        now = timezone.now()
        self.create_post(title="Apple 耳机丢失", occurred_at=now - timedelta(hours=1))
        self.create_post(title="打折100%的打印卡", occurred_at=now - timedelta(hours=1))
        self.create_post(title="a_b 笔记本丢失", occurred_at=now - timedelta(hours=1))

        def count(keyword):
            response = self.client.get("/api/v1/posts", {"keyword": keyword})
            self.assertEqual(response.status_code, 200, response.json())
            return response.json()["data"]["total"]

        self.assertEqual(count("Apple"), 1)
        self.assertEqual(count("apple"), 0)  # 不折叠大小写
        self.assertEqual(count("100%"), 1)  # % 是普通字符
        self.assertEqual(count("%"), 1)
        self.assertEqual(count("_"), 1)  # _ 是普通字符
        self.assertEqual(count("钱包"), 1)  # 命中标题
        self.assertEqual(count("校园卡"), 5)  # 命中描述（默认 5 条可见信息）

    def test_keyword_over_50_chars_is_400(self):
        response = self.client.get("/api/v1/posts", {"keyword": "字" * 51})
        self.assertEqual(response.status_code, 400)
        self.assertIn("keyword", response.json()["errors"])

    def test_blank_keyword_means_no_filter(self):
        response = self.client.get("/api/v1/posts", {"keyword": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["total"], 2)

    def test_filter_by_category_campus_location(self):
        self.create_post(category_id="cat_keys", title="钥匙丢了", occurred_at=timezone.now())
        response = self.client.get("/api/v1/posts", {"category_id": "cat_keys"})
        self.assertEqual(response.json()["data"]["total"], 1)

        response = self.client.get("/api/v1/posts", {"campus_id": "campus_main"})
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/api/v1/posts", {"location_id": "loc_library"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["total"], 3)

    def test_unknown_dict_id_is_400(self):
        for param in ("category_id", "campus_id", "location_id"):
            with self.subTest(param=param):
                response = self.client.get("/api/v1/posts", {param: "nope"})
                self.assertEqual(response.status_code, 400)
                self.assertIn(param, response.json()["errors"])

    def test_location_must_belong_to_campus(self):
        from catalog.models import Campus

        Campus.objects.create(id="campus_b", name="分校区")
        Location.objects.create(id="loc_b", campus_id="campus_b", name="分校区食堂", sort_order=1)
        response = self.client.get(
            "/api/v1/posts", {"campus_id": "campus_main", "location_id": "loc_b"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("location_id", response.json()["errors"])

    def test_occurred_range_is_inclusive_and_validated(self):
        now = timezone.now()
        target = self.create_post(title="区间内的信息", occurred_at=now - timedelta(days=3))
        lower = (now - timedelta(days=4)).isoformat()
        upper = (now - timedelta(days=2)).isoformat()

        response = self.client.get("/api/v1/posts", {"occurred_from": lower, "occurred_to": upper})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), [str(target.id)])

        bad = self.client.get("/api/v1/posts", {"occurred_from": upper, "occurred_to": lower})
        self.assertEqual(bad.status_code, 400)

        malformed = self.client.get("/api/v1/posts", {"occurred_from": "昨天"})
        self.assertEqual(malformed.status_code, 400)
        self.assertIn("occurred_from", malformed.json()["errors"])

    def test_sort_latest_and_occurred_latest(self):
        now = timezone.now()
        late_occurred = self.create_post(
            title="晚发生但先发布",
            occurred_at=now - timedelta(minutes=10),
            created_at=now - timedelta(hours=1),
        )
        early_occurred = self.create_post(
            title="早发生但后发布",
            occurred_at=now - timedelta(hours=10),
            created_at=now,
        )

        latest = self.client.get("/api/v1/posts", {"sort": "latest"})
        self.assertEqual(self.ids(latest)[0], str(early_occurred.id))

        by_occurred = self.client.get("/api/v1/posts", {"sort": "occurred_latest"})
        self.assertEqual(self.ids(by_occurred)[0], str(late_occurred.id))

        invalid = self.client.get("/api/v1/posts", {"sort": "popular"})
        self.assertEqual(invalid.status_code, 400)

    def test_pagination_defaults_and_limits(self):
        for index in range(25):
            self.create_post(title=f"批量信息{index}", occurred_at=timezone.now())

        response = self.client.get("/api/v1/posts", {"page_size": 20})
        data = response.json()["data"]
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 20)
        self.assertEqual(data["total"], 27)  # 25 + 两条默认状态
        self.assertEqual(data["total_pages"], 2)
        self.assertEqual(len(data["items"]), 20)

        second = self.client.get("/api/v1/posts", {"page": 2, "page_size": 20})
        self.assertEqual(len(second.json()["data"]["items"]), 7)

        too_large = self.client.get("/api/v1/posts", {"page_size": 101})
        self.assertEqual(too_large.status_code, 400)
        self.assertIn("page_size", too_large.json()["errors"])

        zero = self.client.get("/api/v1/posts", {"page": 0})
        self.assertEqual(zero.status_code, 400)

        beyond = self.client.get("/api/v1/posts", {"page": 99})
        self.assertEqual(beyond.status_code, 200)
        self.assertEqual(beyond.json()["data"]["items"], [])

    def test_summary_shape(self):
        response = self.client.get("/api/v1/posts")
        item = response.json()["data"]["items"][0]
        self.assertEqual(
            set(item),
            {
                "id",
                "post_type",
                "title",
                "category",
                "campus",
                "location",
                "occurred_at",
                "status",
                "cover_image",
                "publisher",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(set(item["publisher"]), {"id", "nickname", "is_campus_verified", "verification_mode"})
        self.assertIsNone(item["cover_image"])
