from django.db import models
from django.contrib.auth.models import User

class Preset(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='presets')
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    column_config = models.JSONField(default=list)
    datetime_config = models.JSONField(default=dict)
    export_config = models.JSONField(default=dict)
    trigger_pattern = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (by {self.user.username})"
