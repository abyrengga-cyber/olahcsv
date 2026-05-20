from django.urls import path
from .views import PresetListCreateView, PresetDetailView, PresetsPageView

urlpatterns = [
    # Pages
    path('', PresetsPageView.as_view(), name='presets-page'),
    
    # API
    path('api/', PresetListCreateView.as_view(), name='preset-list-create'),
    path('api/<int:pk>/', PresetDetailView.as_view(), name='preset-detail'),
]
