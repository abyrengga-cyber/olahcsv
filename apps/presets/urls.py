from django.urls import path
from .views import PresetListCreateView, PresetDetailView

app_name = "presets"

urlpatterns = [
    path("", PresetListCreateView.as_view(), name="preset-list-create"),
    path("<int:pk>/", PresetDetailView.as_view(), name="preset-detail"),
]
