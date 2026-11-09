from unittest.mock import patch

from common.exceptions import ApiError
from posts.models import Post
from tests.support import BTestCase
from workflow.models import PostStatusHistory
from workflow.transitions import transit


class WithdrawRestoreTests(BTestCase):
    def setUp(self):
        super().setUp()
        self.post = self.create_post()

    def test_withdraw_hides_from_list_and_others(self):
        self.login()
        response = self.client.post(f"/api/v1/posts/{self.post.id}/withdraw")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["data"]["status"], "withdrawn")

        self.logout()
        self.assertEqual(self.client.get("/api/v1/posts").json()["data"]["total"], 0)
        self.assertEqual(self.client.get(f"/api/v1/posts/{self.post.id}").status_code, 404)

        self.login("tok-bob")
        self.assertEqual(self.client.get(f"/api/v1/posts/{self.post.id}").status_code, 404)

        self.login()
        self.assertEqual(self.client.get(f"/api/v1/posts/{self.post.id}").status_code, 200)

    def test_duplicate_withdraw_is_409(self):
        self.login()
        self.client.post(f"/api/v1/posts/{self.post.id}/withdraw")
        again = self.client.post(f"/api/v1/posts/{self.post.id}/withdraw")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()["code"], "STATE_CONFLICT")

    def test_non_owner_cannot_withdraw(self):
        self.login("tok-bob")
        response = self.client.post(f"/api/v1/posts/{self.post.id}/withdraw")
        self.assertEqual(response.status_code, 403)

    def test_restore_makes_post_visible_again(self):
        self.login()
        self.client.post(f"/api/v1/posts/{self.post.id}/withdraw")
        response = self.client.post(f"/api/v1/posts/{self.post.id}/restore")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "open")

        self.logout()
        self.assertEqual(self.client.get("/api/v1/posts").json()["data"]["total"], 1)

    def test_restore_when_open_is_409(self):
        self.login()
        response = self.client.post(f"/api/v1/posts/{self.post.id}/restore")
        self.assertEqual(response.status_code, 409)

    def test_withdraw_records_history_and_keeps_images_readable_only_for_owner(self):
        image = self.create_image(post=self.post)
        self.login()
        self.client.post(f"/api/v1/posts/{self.post.id}/withdraw")
        history = PostStatusHistory.objects.filter(post=self.post).last()
        self.assertEqual((history.from_status, history.to_status), ("open", "withdrawn"))
        self.assertEqual(history.actor_id, "1001")

        self.assertEqual(self.client.get(f"/api/v1/post-images/{image.id}/content").status_code, 200)
        self.logout()
        self.assertEqual(self.client.get(f"/api/v1/post-images/{image.id}/content").status_code, 404)

    def test_withdraw_rolls_back_when_c_service_fails(self):
        self.login()
        with patch(
            "posts.views.close_pending_claims",
            side_effect=ApiError(503, "UPSTREAM_UNAVAILABLE", "认领服务暂不可用，信息状态未改变"),
        ):
            response = self.client.post(f"/api/v1/posts/{self.post.id}/withdraw")
        self.assertEqual(response.status_code, 503)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, "open")
        self.assertEqual(PostStatusHistory.objects.filter(post=self.post).count(), 0)

    def test_withdraw_calls_c_service_when_configured(self):
        self.login()
        with patch("posts.views.close_pending_claims", return_value={"closed": 1}) as mocked:
            response = self.client.post(f"/api/v1/posts/{self.post.id}/withdraw")
        self.assertEqual(response.status_code, 200)
        mocked.assert_called_once()
        args, kwargs = mocked.call_args
        self.assertEqual(args[0], self.post.id)
        self.assertEqual(kwargs.get("reason"), "post_withdrawn")


class ResolveReopenTests(BTestCase):
    def test_resolve_lost_success(self):
        post = self.create_post()
        self.login()
        response = self.client.post(
            f"/api/v1/posts/{post.id}/resolve",
            {"resolve_note": "已在图书馆服务台找回，工作人员核对后归还"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()["data"]
        self.assertEqual(data["status"], "completed")
        self.assertIsNotNone(data["completed_at"])

        history = PostStatusHistory.objects.filter(post=post).last()
        self.assertEqual(history.to_status, "completed")
        self.assertEqual(history.actor_id, "1001")
        self.assertIn("服务台", history.reason)

    def test_resolve_note_length_is_checked(self):
        post = self.create_post()
        self.login()
        for note in ("", "太短", "字" * 201):
            with self.subTest(note=note):
                response = self.client.post(
                    f"/api/v1/posts/{post.id}/resolve", {"resolve_note": note}, format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("resolve_note", response.json()["errors"])

    def test_found_cannot_resolve(self):
        post = self.create_post(post_type="found")
        self.login()
        response = self.client.post(
            f"/api/v1/posts/{post.id}/resolve",
            {"resolve_note": "想直接标记完成，但招领必须走认领流程"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_resolve_twice_is_409(self):
        post = self.create_post()
        self.login()
        self.client.post(
            f"/api/v1/posts/{post.id}/resolve",
            {"resolve_note": "已经通过其他方式找回物品"},
            format="json",
        )
        again = self.client.post(
            f"/api/v1/posts/{post.id}/resolve",
            {"resolve_note": "再次标记找回应当冲突"},
            format="json",
        )
        self.assertEqual(again.status_code, 409)

    def test_reopen_completed_without_claim(self):
        post = self.create_post(status="completed")
        self.login()
        with patch("posts.views.has_completed_claim", return_value=False):
            response = self.client.post(f"/api/v1/posts/{post.id}/reopen")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["data"]["status"], "open")
        self.assertIsNone(response.json()["data"]["completed_at"])

    def test_reopen_blocked_when_completed_claim_exists(self):
        post = self.create_post(status="completed")
        self.login()
        with patch("posts.views.has_completed_claim", return_value=True):
            response = self.client.post(f"/api/v1/posts/{post.id}/reopen")
        self.assertEqual(response.status_code, 409)
        post.refresh_from_db()
        self.assertEqual(post.status, "completed")

    def test_reopen_requires_completed_status(self):
        post = self.create_post()
        self.login()
        response = self.client.post(f"/api/v1/posts/{post.id}/reopen")
        self.assertEqual(response.status_code, 409)


class TransitMatrixTests(BTestCase):
    def test_duplicate_transition_is_409(self):
        post = self.create_post(status="withdrawn")
        with self.assertRaises(ApiError) as ctx:
            transit(post, "withdrawn", "1001")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_illegal_jump_is_409(self):
        post = self.create_post(status="withdrawn")
        with self.assertRaises(ApiError) as ctx:
            transit(post, "completed", "1001")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_found_cannot_be_completed_from_open(self):
        post = self.create_post(post_type="found")
        with self.assertRaises(ApiError) as ctx:
            transit(post, "completed", "1001")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_completed_clears_completed_at_on_reopen(self):
        post = self.create_post(status="completed")
        post.completed_at = post.occurred_at
        post.save(update_fields=["completed_at"])
        transit(post, "open", "1001")
        post.refresh_from_db()
        self.assertIsNone(post.completed_at)
        self.assertEqual(post.status, "open")
