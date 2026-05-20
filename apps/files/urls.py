from django.urls import path
from .views import FileUploadView, PreviewFileView

app_name = 'files'

urlpatterns = [
    path('api/files/upload/', FileUploadView.as_view(), name='file-upload'),
    path('api/files/<int:file_id>/preview/', PreviewFileView.as_view(), name='file-preview'),
]
