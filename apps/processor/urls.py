from django.urls import path
from .views import AggregationView, ComparisonView

urlpatterns = [
    path("processor/aggregate/", AggregationView.as_view(), name="api_aggregate"),
    path("processor/compare/", ComparisonView.as_view(), name="api_compare"),
]
