from django.contrib import admin
from .models import ExportJob


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "format", "status", "created_at", "completed_at")
    list_filter = ("format", "status", "created_at")
    search_fields = ("session__user__username",)
    date_hierarchy = "created_at"
