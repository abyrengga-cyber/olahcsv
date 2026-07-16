from rest_framework import serializers
from .models import UploadedFile


class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = (
            "id",
            "original_filename",
            "file_path",
            "file_size",
            "delimiter",
            "encoding",
            "row_count",
            "column_count",
            "upload_at",
            "status",
        )
        read_only_fields = (
            "id",
            "user",
            "file_size",
            "row_count",
            "column_count",
            "delimiter",
            "encoding",
            "status",
            "upload_at",
        )
        extra_kwargs = {
            "file_path": {"read_only": True},
        }
