import io
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from apps.presets.models import Preset


class PresetAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client.force_authenticate(user=self.user)
        self.list_url = reverse("preset-list-create")

    def test_list_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_preset(self):
        resp = self.client.post(
            self.list_url,
            {
                "name": "My Preset",
                "column_config": [{"name": "col1", "include": True}],
                "datetime_config": {},
                "export_config": {"format": "csv"},
                "trigger_pattern": {},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Preset.objects.count(), 1)
        self.assertEqual(Preset.objects.first().name, "My Preset")

    def test_list_user_presets_only(self):
        other = User.objects.create_user(username="other", password="testpass123")
        Preset.objects.create(user=other, name="Other's Preset")
        Preset.objects.create(user=self.user, name="My Preset")

        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["name"], "My Preset")

    def test_detail_requires_auth(self):
        preset = Preset.objects.create(user=self.user, name="Test")
        url = reverse("preset-detail", args=[preset.pk])
        self.client.force_authenticate(user=None)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_detail_owner_only(self):
        preset = Preset.objects.create(user=self.user, name="Test")
        other = User.objects.create_user(username="other", password="testpass123")
        self.client.force_authenticate(user=other)
        url = reverse("preset-detail", args=[preset.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_owner_only(self):
        preset = Preset.objects.create(user=self.user, name="Old Name")
        other = User.objects.create_user(username="other", password="testpass123")
        self.client.force_authenticate(user=other)
        url = reverse("preset-detail", args=[preset.pk])
        resp = self.client.patch(url, {"name": "Hacked"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_owner_only(self):
        preset = Preset.objects.create(user=self.user, name="To Delete")
        other = User.objects.create_user(username="other", password="testpass123")
        self.client.force_authenticate(user=other)
        url = reverse("preset-detail", args=[preset.pk])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Preset.objects.count(), 1)

    def test_update_preset(self):
        preset = Preset.objects.create(user=self.user, name="Old Name")
        url = reverse("preset-detail", args=[preset.pk])
        resp = self.client.patch(url, {"name": "New Name"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Preset.objects.get(pk=preset.pk).name, "New Name")

    def test_delete_preset(self):
        preset = Preset.objects.create(user=self.user, name="To Delete")
        url = reverse("preset-detail", args=[preset.pk])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Preset.objects.count(), 0)
