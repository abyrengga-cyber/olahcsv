import io
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status


class AggregationAPITest(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        upload_resp = self.client.post(
            reverse("files:file-upload"),
            {"file": io.BytesIO(b"category,value\nA,10\nA,20\nB,30\nB,40")},
            format="multipart",
        )
        self.file_id = upload_resp.data["files"][0]["id"]
        self.aggregate_url = reverse("api_aggregate")

    def test_aggregate_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            self.aggregate_url,
            {"file_id": self.file_id, "columns": ["value"], "types": ["SUM"]},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_aggregate_owner_only(self):
        other = User.objects.create_user(username="other", password="testpass123")
        self.client.force_authenticate(user=other)
        resp = self.client.post(
            self.aggregate_url,
            {"file_id": self.file_id, "columns": ["value"], "types": ["SUM"]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_aggregate_missing_params(self):
        resp = self.client.post(self.aggregate_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_aggregate_sum(self):
        resp = self.client.post(
            self.aggregate_url,
            {"file_id": self.file_id, "columns": ["value"], "types": ["SUM"]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"][0]["value_SUM"], 100)

    def test_aggregate_with_group_by(self):
        resp = self.client.post(
            self.aggregate_url,
            {
                "file_id": self.file_id,
                "columns": ["value"],
                "types": ["SUM"],
                "group_by": "category",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rows = {r["category"]: r["value_sum"] for r in resp.data["data"]}
        self.assertEqual(rows["A"], 30)
        self.assertEqual(rows["B"], 70)

    def test_aggregate_multiple_types(self):
        resp = self.client.post(
            self.aggregate_url,
            {"file_id": self.file_id, "columns": ["value"], "types": ["SUM", "COUNT"]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("value_SUM", resp.data["data"][0])
        self.assertIn("value_COUNT", resp.data["data"][0])


class ComparisonAPITest(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        upload_resp = self.client.post(
            reverse("files:file-upload"),
            {"file": io.BytesIO(b"col_a,col_b\n100,50\n200,100\n300,150")},
            format="multipart",
        )
        self.file_id = upload_resp.data["files"][0]["id"]
        self.compare_url = reverse("api_compare")

    def test_compare_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            self.compare_url,
            {
                "file_id": self.file_id,
                "col_a": "col_a",
                "col_b": "col_b",
                "calc_type": "pct_diff",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_compare_owner_only(self):
        other = User.objects.create_user(username="other", password="testpass123")
        self.client.force_authenticate(user=other)
        resp = self.client.post(
            self.compare_url,
            {
                "file_id": self.file_id,
                "col_a": "col_a",
                "col_b": "col_b",
                "calc_type": "pct_diff",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compare_missing_params(self):
        resp = self.client.post(self.compare_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compare_pct_diff(self):
        resp = self.client.post(
            self.compare_url,
            {
                "file_id": self.file_id,
                "col_a": "col_a",
                "col_b": "col_b",
                "calc_type": "pct_diff",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"][0]["result"], 100.0)

    def test_compare_ratio(self):
        resp = self.client.post(
            self.compare_url,
            {
                "file_id": self.file_id,
                "col_a": "col_a",
                "col_b": "col_b",
                "calc_type": "ratio",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"][0]["result"], 200.0)

    def test_compare_pct_contrib(self):
        resp = self.client.post(
            self.compare_url,
            {
                "file_id": self.file_id,
                "col_a": "col_a",
                "col_b": "col_b",
                "calc_type": "pct_contrib",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(resp.data["data"][0]["result"], 100 / 6, places=2)

    def test_compare_invalid_calc_type(self):
        resp = self.client.post(
            self.compare_url,
            {
                "file_id": self.file_id,
                "col_a": "col_a",
                "col_b": "col_b",
                "calc_type": "invalid",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compare_creates_new_file(self):
        from apps.files.models import UploadedFile

        before = UploadedFile.objects.count()
        resp = self.client.post(
            self.compare_url,
            {
                "file_id": self.file_id,
                "col_a": "col_a",
                "col_b": "col_b",
                "calc_type": "pct_diff",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp.data.get("new_file_id"))
        self.assertEqual(UploadedFile.objects.count(), before + 1)
