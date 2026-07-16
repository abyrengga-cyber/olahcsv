from django.urls import path
from .views import AggregationView, ComparisonView, DateTimeView, ChartDataView

app_name = "processor"

urlpatterns = [
    path("processor/aggregate/", AggregationView.as_view(), name="api_aggregate"),
    path("processor/compare/", ComparisonView.as_view(), name="api_compare"),
    path("processor/datetime/", DateTimeView.as_view(), name="api_datetime"),
    path("processor/chart-data/", ChartDataView.as_view(), name="api_chart_data"),
]
