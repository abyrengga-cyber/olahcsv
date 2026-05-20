from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from apps.accounts.views import dashboard, workspace_view, register_view


urlpatterns = [
    path('admin/', admin.site.urls),

    # Main Pages
    path('', dashboard, name='dashboard'),
    path('workspace/', workspace_view, name='workspace'),
    
    # APIs
    path('', include('apps.files.urls')),
    path('', include('apps.export.urls')),
    path('', include('apps.processor.urls')),
    path('presets/', include('apps.presets.urls')),

    # Auth
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html'
    ), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/register/', register_view, name='register'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
