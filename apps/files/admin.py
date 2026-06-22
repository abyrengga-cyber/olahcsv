from django.contrib import admin
from .models import UploadedFile


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "user", "file_size", "status", "upload_at")
    list_filter = ("status", "upload_at")
    search_fields = ("original_filename", "user__username")
    date_hierarchy = "upload_at"
