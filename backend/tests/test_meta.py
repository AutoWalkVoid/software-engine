from catalog.models import Campus, Category, Location
from tests.support import BTestCase


class MetaApiTests(BTestCase):
    def test_campuses_anon_returns_seed(self):
        response = self.client.get("/api/v1/meta/campuses")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], "OK")
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0], {"id": "campus_main", "name": "主校区"})

    def test_categories_returns_six_seed_rows_sorted(self):
        response = self.client.get("/api/v1/meta/categories")
        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]
        self.assertEqual(len(items), 6)
        self.assertEqual([item["id"] for item in items][:2], ["cat_document", "cat_electronics"])
        self.assertEqual(items[0]["sort_order"], 10)

    def test_locations_returns_five_and_supports_campus_filter(self):
        all_items = self.client.get("/api/v1/meta/locations").json()["data"]
        self.assertEqual(len(all_items), 5)

        filtered = self.client.get("/api/v1/meta/locations", {"campus_id": "campus_main"}).json()
        self.assertEqual(len(filtered["data"]), 5)
        self.assertTrue(all(item["campus_id"] == "campus_main" for item in filtered["data"]))

    def test_locations_unknown_campus_is_400(self):
        response = self.client.get("/api/v1/meta/locations", {"campus_id": "campus_nope"})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["code"], "VALIDATION_ERROR")
        self.assertIn("campus_id", body["errors"])

    def test_seed_counts_match_models(self):
        self.assertEqual(Campus.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(Location.objects.count(), 5)


class RoutingTests(BTestCase):
    def test_unknown_api_path_returns_json_404(self):
        response = self.client.get("/api/v1/nope/nothing")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["code"], "NOT_FOUND")
        self.assertIsNone(body["data"])

    def test_non_numeric_post_id_returns_json_404(self):
        response = self.client.get("/api/v1/posts/abc")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_trailing_slash_is_not_accepted(self):
        response = self.client.get("/api/v1/posts/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "NOT_FOUND")
