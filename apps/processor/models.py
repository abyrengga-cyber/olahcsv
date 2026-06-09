from django.db import models
from django.contrib.auth.models import User
from apps.files.models import UploadedFile


class ProcessingSession(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="processing_sessions"
    )
    files = models.ManyToManyField(UploadedFile, related_name="sessions")
    configuration = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="ACTIVE")

    def __str__(self):
        return f"Session {self.id} for {self.user.username}"
