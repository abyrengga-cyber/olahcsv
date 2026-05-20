from django.urls import path
from .views import AggregationView, ComparisonView

urlpatterns = [
    path('api/processor/aggregate/', AggregationView.as_view(), name='api_aggregate'),
    path('api/processor/compare/', ComparisonView.as_view(), name='api_compare'),
]
