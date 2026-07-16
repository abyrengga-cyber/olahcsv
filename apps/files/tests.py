import os
import tempfile
import io
from django.test import TestCase
from django.core.cache import cache
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from apps.files.utils import detect_encoding, detect_delimiter, parse_file_metadata
from apps.files.models import UploadedFile


class FilesUtilsTest(TestCase):
    def setUp(self):
        self.temp_csv = tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv", mode="w", encoding="utf-8"
        )
        self.temp_csv.write("id,name,age\n1,Alice,30\n2,Bob,25\n3,Charlie,35")
        self.temp_csv.close()

        self.temp_tsv = tempfile.NamedTemporaryFile(
            delete=False, suffix=".txt", mode="w", encoding="utf-8"
        )
        self.temp_tsv.write("id\tname\tage\n1\tAlice\t30\n2\tBob\t25\n3\tCharlie\t35")
        self.temp_tsv.close()

    def tearDown(self):
        os.unlink(self.temp_csv.name)
        os.unlink(self.temp_tsv.name)

    def test_detect_encoding(self):
        enc = detect_encoding(self.temp_csv.name)
        self.assertIn(enc.lower(), ["ascii", "utf-8"])

    def test_detect_delimiter(self):
        self.assertEqual(detect_delimiter(self.temp_csv.name, "utf-8"), ",")
        self.assertEqual(detect_delimiter(self.temp_tsv.name, "utf-8"), "\t")

    def test_parse_file_metadata(self):
        metadata = parse_file_metadata(self.temp_csv.name)
        self.assertTrue(metadata["success"])
        self.assertEqual(metadata["delimiter"], ",")
        self.assertEqual(metadata["row_count"], 3)
        self.assertEqual(metadata["column_count"], 3)

        columns = [c["name"] for c in metadata["columns"]]
        self.assertEqual(columns, ["id", "name", "age"])

        self.assertEqual(len(metadata["preview"]), 3)
        self.assertEqual(metadata["preview"][0]["name"], "Alice")


class FileUploadAPITest(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        self.upload_url = reverse("files:file-upload")

    def _make_csv(self, content="a,b\n1,2\n3,4", name="test.csv"):
        return io.BytesIO(content.encode("utf-8"))

    def test_upload_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            self.upload_url, {"file": self._make_csv()}, format="multipart"
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_success(self):
        resp = self.client.post(
            self.upload_url, {"file": self._make_csv()}, format="multipart"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data["files"]), 1)
        self.assertEqual(resp.data["files"][0]["metadata"]["row_count"], 2)
        self.assertEqual(UploadedFile.objects.count(), 1)

    def test_upload_multiple_files(self):
        files = [
            self._make_csv("a\n1\n2", "f1.csv"),
            self._make_csv("b\n3\n4", "f2.csv"),
        ]
        resp = self.client.post(self.upload_url, {"file": files}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data["files"]), 2)
        self.assertEqual(UploadedFile.objects.count(), 2)

    def test_upload_no_file(self):
        resp = self.client.post(self.upload_url, {}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_xlsx(self):
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["name", "val"])
        ws.append(["A", 10])
        ws.append(["B", 20])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = "test.xlsx"

        resp = self.client.post(self.upload_url, {"file": buf}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.data["files"]), 1)
        self.assertEqual(resp.data["files"][0]["metadata"]["row_count"], 2)


class FilePreviewAPITest(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        self.upload_url = reverse("files:file-upload")

        resp = self.client.post(
            self.upload_url,
            {"file": io.BytesIO(b"name,val\nA,10\nB,20\nC,30")},
            format="multipart",
        )
        self.file_id = resp.data["files"][0]["id"]
        self.preview_url = reverse("files:file-preview", args=[self.file_id])

    def test_preview_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.preview_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_preview_owner_only(self):
        other = User.objects.create_user(username="other", password="testpass123")
        self.client.force_authenticate(user=other)
        resp = self.client.get(self.preview_url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_preview_success(self):
        resp = self.client.get(self.preview_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(len(resp.data["preview"]), 3)
        self.assertEqual(resp.data["columns"][0]["name"], "name")

    def test_preview_pagination(self):
        resp = self.client.get(self.preview_url, {"page": 1, "page_size": 2})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["preview"]), 2)

    def test_preview_sorting(self):
        resp = self.client.get(
            self.preview_url, {"sort_by": "val", "sort_order": "desc"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["preview"][0]["val"], 30)

    def test_preview_filtering(self):
        resp = self.client.get(
            self.preview_url, {"filter_col": "name", "filter_query": "A"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["preview"]), 1)
        self.assertEqual(resp.data["preview"][0]["name"], "A")


class FileDeleteAPITest(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)

        resp = self.client.post(
            reverse("files:file-upload"),
            {"file": io.BytesIO(b"a,b\n1,2")},
            format="multipart",
        )
        self.file_id = resp.data["files"][0]["id"]
        self.delete_url = reverse("files:file-delete", args=[self.file_id])

    def test_delete_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.delete(self.delete_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_owner_only(self):
        other = User.objects.create_user(username="other", password="testpass123")
        self.client.force_authenticate(user=other)
        resp = self.client.delete(self.delete_url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_success(self):
        resp = self.client.delete(self.delete_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(UploadedFile.objects.count(), 0)

    def test_delete_nonexistent(self):
        url = reverse("files:file-delete", args=[9999])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
