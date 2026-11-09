from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from integration import for_c
from integration.users import get_user_summaries
from posts.models import Post
from tests.support import BTestCase


class AuthTests(BTestCase):
    def test_missing_token_is_401(self):
        response = self.client.post("/api/v1/posts", self.post_payload(), format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "UNAUTHENTICATED")

    def test_unknown_token_is_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer tok-nobody")
        response = self.client.post("/api/v1/posts", self.post_payload(), format="json")
        self.assertEqual(response.status_code, 401)

    def test_malformed_header_is_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token tok-alice")
        response = self.client.post("/api/v1/posts", self.post_payload(), format="json")
        self.assertEqual(response.status_code, 401)

    def test_identity_service_down_is_401_and_logged(self):
        from integration.auth import IdentityUnavailable

        self.login()
        with patch("integration.auth.fetch_identity", side_effect=IdentityUnavailable("boom")):
            with self.assertLogs("b.auth", level="ERROR") as logs:
                response = self.client.post("/api/v1/posts", self.post_payload(), format="json")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(any("身份服务不可用" in line for line in logs.output))

    def test_anonymous_public_list_still_works(self):
        self.assertEqual(self.client.get("/api/v1/posts").status_code, 200)

    def test_user_summaries_come_from_publish_snapshot(self):
        self.create_post(publisher_id="1001")
        summaries = get_user_summaries(["1001", "1002"])
        self.assertEqual(summaries["1001"]["nickname"], "小林")
        self.assertTrue(summaries["1001"]["is_campus_verified"])
        self.assertNotIn("1002", summaries)  # A 未提供、B 也无发布快照


class ForCTests(BTestCase):
    def test_get_post_for_claim_returns_post_and_publisher(self):
        post = self.create_post()
        result = for_c.get_post_for_claim(post.id)
        self.assertEqual(result["post"].id, post.id)
        self.assertEqual(result["post_id"], str(post.id))
        self.assertEqual(result["publisher"]["id"], "1001")

    def test_get_post_for_claim_missing_is_404(self):
        from common.exceptions import ApiError

        with self.assertRaises(ApiError) as ctx:
            for_c.get_post_for_claim(99999)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_set_handover_state_flow(self):
        post = self.create_post()
        for_c.set_handover_state(post.id, "reserve", actor="claim-service")
        post.refresh_from_db()
        self.assertEqual(post.status, "in_handover")

        for_c.set_handover_state(post.id, "complete")
        post.refresh_from_db()
        self.assertEqual(post.status, "completed")
        self.assertIsNotNone(post.completed_at)

    def test_set_handover_state_cancel_reopens(self):
        post = self.create_post(status="in_handover")
        for_c.set_handover_state(post.id, "reopen")
        post.refresh_from_db()
        self.assertEqual(post.status, "open")

    def test_set_handover_state_rejects_unknown_transition(self):
        from common.exceptions import ApiError

        post = self.create_post()
        with self.assertRaises(ApiError) as ctx:
            for_c.set_handover_state(post.id, "teleport")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_set_handover_state_rejects_wrong_current_status(self):
        from common.exceptions import ApiError

        post = self.create_post(status="in_handover")
        with self.assertRaises(ApiError) as ctx:
            for_c.set_handover_state(post.id, "reserve")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_match_candidates_rules_and_scores(self):
        now = timezone.now()
        source = self.create_post(
            title="黑色钱包丢失",
            occurred_at=now - timedelta(hours=2),
            category_id="cat_other",
            location_id="loc_library",
        )
        best = self.create_post(
            post_type="found",
            publisher_id="1003",
            title="黑色钱包已拾到",
            occurred_at=now - timedelta(hours=1),
            location_id="loc_library",
        )
        far_location = self.create_post(
            post_type="found",
            publisher_id="1003",
            title="黑色钱包在食堂被捡到",
            occurred_at=now - timedelta(hours=1),
            location_id="loc_canteen",
        )
        too_late = self.create_post(
            post_type="found",
            publisher_id="1003",
            title="黑色钱包很久以后才被捡到",
            occurred_at=now + timedelta(days=40),
            location_id="loc_library",
        )
        self.create_post(
            post_type="found",
            publisher_id="1003",
            title="无关物品",
            status="withdrawn",
            location_id="loc_library",
        )
        self.create_post(post_type="lost", title="黑色钱包也丢了", location_id="loc_library")
        self.create_post(
            post_type="found",
            publisher_id="1003",
            title="黑色钱包（别的类别）",
            category_id="cat_keys",
            location_id="loc_library",
        )

        candidates = for_c.list_match_candidates(source)
        ids = [item["post"].id for item in candidates]
        self.assertEqual(ids[0], best.id)  # 100 分：类别+地点+时间+关键词
        self.assertEqual(candidates[0]["score"], 100)
        self.assertEqual(
            candidates[0]["reasons"],
            ["category_same", "location_same", "time_near", "keyword_overlap"],
        )
        self.assertIn(far_location.id, ids)
        self.assertNotIn(too_late.id, ids)
        self.assertEqual(len(candidates), 2)
        self.assertLess(candidates[1]["score"], candidates[0]["score"])

    def test_match_candidates_limit(self):
        now = timezone.now()
        source = self.create_post(title="黑色钱包丢失", occurred_at=now - timedelta(hours=2))
        for index in range(4):
            self.create_post(
                post_type="found",
                publisher_id="1003",
                title=f"黑色钱包第{index}次被捡到",
                occurred_at=now - timedelta(hours=1),
            )
        self.assertEqual(len(for_c.list_match_candidates(source, limit=2)), 2)

    def test_match_candidates_excludes_withdrawn_and_completed(self):
        now = timezone.now()
        source = self.create_post(title="黑色钱包丢失", occurred_at=now - timedelta(hours=2))
        self.create_post(
            post_type="found", publisher_id="1003", title="黑色钱包已交接", status="completed"
        )
        self.create_post(
            post_type="found", publisher_id="1003", title="黑色钱包已撤回", status="withdrawn"
        )
        self.assertEqual(for_c.list_match_candidates(source), [])

    def test_match_candidates_for_found_source(self):
        now = timezone.now()
        found = self.create_post(
            post_type="found", title="拾到钥匙", occurred_at=now - timedelta(hours=1)
        )
        lost = self.create_post(
            publisher_id="1003",
            title="钥匙丢了",
            occurred_at=now - timedelta(hours=3),
            category_id="cat_other",
        )
        candidates = for_c.list_match_candidates(found)
        self.assertEqual([item["post"].id for item in candidates], [lost.id])
