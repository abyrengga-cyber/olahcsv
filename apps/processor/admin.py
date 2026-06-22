from django.contrib import admin
from .models import ProcessingSession


@admin.register(ProcessingSession)
class ProcessingSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"
