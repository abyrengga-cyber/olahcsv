from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts.views import (
    dashboard,
    workspace_view,
    register_view,
    dashboard_chart_data,
)
from apps.presets.views import PresetsPageView


urlpatterns = [
    path("admin/", admin.site.urls),
    # Main Pages
    path("", dashboard, name="dashboard"),
    path("api/v1/dashboard/chart/", dashboard_chart_data, name="dashboard-chart"),
    path("workspace/", workspace_view, name="workspace"),
    # Page: Presets
    path("presets/", PresetsPageView.as_view(), name="presets-page"),
    # APIs (versioned)
    path("api/v1/", include("apps.files.urls")),
    path("api/v1/", include("apps.export.urls")),
    path("api/v1/", include("apps.processor.urls")),
    path("api/v1/presets/", include("apps.presets.urls")),
    # Auth
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", register_view, name="register"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
