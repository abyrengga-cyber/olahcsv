from django.urls import path
from .views import FileUploadView, PreviewFileView, FileDeleteView, ColumnValuesView

app_name = "files"

urlpatterns = [
    path("files/upload/", FileUploadView.as_view(), name="file-upload"),
    path(
        "files/<int:file_id>/preview/", PreviewFileView.as_view(), name="file-preview"
    ),
    path("files/<int:file_id>/delete/", FileDeleteView.as_view(), name="file-delete"),
    path(
        "files/<int:file_id>/column-values/",
        ColumnValuesView.as_view(),
        name="file-column-values",
    ),
]
