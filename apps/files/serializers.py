from rest_framework import serializers
from .models import UploadedFile

class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = '__all__'
        read_only_fields = ('user', 'file_size', 'row_count', 'column_count', 'delimiter', 'encoding', 'status')
