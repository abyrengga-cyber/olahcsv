from django.db import models
from django.contrib.auth.models import User

class UploadedFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_files')
    original_filename = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='uploads/%Y/%m/%d/')
    file_size = models.BigIntegerField()
    delimiter = models.CharField(max_length=10, blank=True, null=True)
    encoding = models.CharField(max_length=50, blank=True, null=True)
    row_count = models.IntegerField(null=True, blank=True)
    column_count = models.IntegerField(null=True, blank=True)
    upload_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='UPLOADED')  # UPLOADED, PROCESSING, READY, ERROR

    def __str__(self):
        return f"{self.original_filename} ({self.status})"

from django.db.models.signals import post_delete
from django.dispatch import receiver
import os

@receiver(post_delete, sender=UploadedFile)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """Menghapus file dari filesystem ketika instance `UploadedFile` dihapus."""
    if instance.file_path:
        if os.path.isfile(instance.file_path.path):
            os.remove(instance.file_path.path)
