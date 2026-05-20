from django.urls import path
from .views import ExportDataView

app_name = 'export'

urlpatterns = [
    path('api/export/', ExportDataView.as_view(), name='export-data'),
]
