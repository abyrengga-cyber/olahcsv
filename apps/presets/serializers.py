from rest_framework import serializers
from .models import Preset

class PresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preset
        fields = ['id', 'user', 'name', 'description', 'column_config', 'datetime_config', 'export_config', 'trigger_pattern', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
