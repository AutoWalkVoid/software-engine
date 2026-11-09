from django.core.files.uploadedfile import SimpleUploadedFile

from posts.models import PostImage
from tests.support import PNG_BYTES, BTestCase


def upload(name="a.png", content=PNG_BYTES, content_type="image/png", **form):
    payload = {"file": SimpleUploadedFile(name, content, content_type=content_type)}
    payload.update(form)
    return payload


class ImageUploadTests(BTestCase):
    def test_upload_ok_returns_image_view(self):
        self.login()
        response = self.client.post(
            "/api/v1/post-images",
            upload(alt_text="黑色皮质钱包，有一个白色拉链头"),
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual(data["mime_type"], "image/png")
        self.assertEqual(data["size_bytes"], len(PNG_BYTES))
        self.assertEqual(data["sort_order"], 0)
        self.assertTrue(data["is_public"])
        self.assertEqual(data["url"], f"/api/v1/post-images/{data['id']}/content")
        image = PostImage.objects.get(pk=int(data["id"]))
        self.assertEqual(image.owner_id, "1001")
        self.assertTrue(image.file.name.startswith("post-images/"))

    def test_upload_requires_login(self):
        response = self.client.post("/api/v1/post-images", upload(alt_text="黑色皮质钱包，有白色拉链"))
        self.assertEqual(response.status_code, 401)

    def test_alt_text_length_is_checked(self):
        self.login()
        for alt_text in ("图", "字" * 101, "   "):
            with self.subTest(alt_text=alt_text):
                response = self.client.post("/api/v1/post-images", upload(alt_text=alt_text))
                self.assertEqual(response.status_code, 400)
                self.assertIn("alt_text", response.json()["errors"])

    def test_is_public_must_be_boolean(self):
        self.login()
        response = self.client.post(
            "/api/v1/post-images", upload(alt_text="黑色皮质钱包，有白色拉链", is_public="maybe")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("is_public", response.json()["errors"])

    def test_is_public_false_is_accepted(self):
        self.login()
        response = self.client.post(
            "/api/v1/post-images", upload(alt_text="黑色皮质钱包，有白色拉链", is_public="false")
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["data"]["is_public"])

    def test_file_too_large_is_413(self):
        self.login()
        big = b"\x00" * (5 * 1024 * 1024 + 1)
        response = self.client.post(
            "/api/v1/post-images", upload(content=big, alt_text="黑色皮质钱包，有白色拉链")
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["code"], "FILE_TOO_LARGE")

    def test_unsupported_format_is_415(self):
        self.login()
        response = self.client.post(
            "/api/v1/post-images",
            upload(name="fake.png", content=b"not an image at all", alt_text="黑色皮质钱包，有白色拉链"),
        )
        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["code"], "UNSUPPORTED_MEDIA_TYPE")


class ImageVisibilityTests(BTestCase):
    def test_public_bound_image_is_anonymous_readable(self):
        post = self.create_post()
        image = self.create_image(post=post, is_public=True)
        response = self.client.get(f"/api/v1/post-images/{image.id}/content")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_private_image_requires_login(self):
        post = self.create_post()
        image = self.create_image(post=post, is_public=False)
        anonymous = self.client.get(f"/api/v1/post-images/{image.id}/content")
        self.assertEqual(anonymous.status_code, 401)

        self.login("tok-bob")
        logged_in = self.client.get(f"/api/v1/post-images/{image.id}/content")
        self.assertEqual(logged_in.status_code, 200)

    def test_unbound_image_only_owner_can_read(self):
        image = self.create_image(owner_id="1001")
        self.login("tok-bob")
        self.assertEqual(self.client.get(f"/api/v1/post-images/{image.id}/content").status_code, 404)

        self.login("tok-alice")
        self.assertEqual(self.client.get(f"/api/v1/post-images/{image.id}/content").status_code, 200)

    def test_withdrawn_post_images_only_publisher(self):
        post = self.create_post(status="withdrawn")
        image = self.create_image(post=post, is_public=True)

        self.logout()
        self.assertEqual(self.client.get(f"/api/v1/post-images/{image.id}/content").status_code, 404)

        self.login("tok-bob")
        self.assertEqual(self.client.get(f"/api/v1/post-images/{image.id}/content").status_code, 404)

        self.login("tok-alice")
        self.assertEqual(self.client.get(f"/api/v1/post-images/{image.id}/content").status_code, 200)

    def test_missing_image_is_404(self):
        self.assertEqual(self.client.get("/api/v1/post-images/99999/content").status_code, 404)
