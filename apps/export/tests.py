import io
import os
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status
from apps.export.models import ExportJob


class ExportAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        upload_resp = self.client.post(
            reverse("files:file-upload"),
            {"file": io.BytesIO(b"name,val\nA,10\nB,20\nC,30")},
            format="multipart",
        )
        self.file_id = upload_resp.data["files"][0]["id"]
        self.export_url = reverse("export:export-data")

    def test_export_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            self.export_url, {"file_ids": [self.file_id], "format": "csv"}
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_csv(self):
        resp = self.client.post(
            self.export_url,
            {"file_ids": [self.file_id], "format": "csv"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["filename"].endswith(".csv"))
        self.assertIn("url", resp.data)

    def test_export_xlsx(self):
        resp = self.client.post(
            self.export_url,
            {"file_ids": [self.file_id], "format": "xlsx"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["filename"].endswith(".xlsx"))
        self.assertEqual(resp.data["sheets"], ["Data"])

    def test_export_with_filtered_scope(self):
        resp = self.client.post(
            self.export_url,
            {
                "file_ids": [self.file_id],
                "format": "csv",
                "export_scope": "filtered",
                "filter_col": "name",
                "filter_query": "A",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_export_with_sort(self):
        resp = self.client.post(
            self.export_url,
            {
                "file_ids": [self.file_id],
                "format": "csv",
                "sort_by": "val",
                "sort_order": "desc",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_export_with_column_selection(self):
        resp = self.client.post(
            self.export_url,
            {
                "file_ids": [self.file_id],
                "format": "csv",
                "columns": [{"name": "name", "include": True, "alias": "Nama"}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_export_no_file_ids(self):
        resp = self.client.post(
            self.export_url, {"file_ids": [], "format": "csv"}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_records_export_job(self):
        before = ExportJob.objects.count()
        resp = self.client.post(
            self.export_url,
            {"file_ids": [self.file_id], "format": "csv"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(ExportJob.objects.count(), before + 1)

    def test_export_xlsx_with_aggregation_sheet(self):
        resp = self.client.post(
            self.export_url,
            {
                "file_ids": [self.file_id],
                "format": "xlsx",
                "aggregation_result": [{"col": "val", "total": 60}],
                "aggregation_columns": ["col", "total"],
                "include_aggregation": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("Agregasi", resp.data["sheets"])
