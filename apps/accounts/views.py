from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required


from apps.files.models import UploadedFile
from apps.presets.models import Preset
from apps.export.models import ExportJob
from django.db.models import Sum

def dashboard(request):
    """Landing page with upload zone, stats, recent files."""
    if not request.user.is_authenticated:
        return render(request, 'dashboard.html', {
            'total_files': 0, 'total_columns': 0, 'total_exports': 0, 'total_presets': 0,
            'recent_files': [], 'recent_presets': []
        })

    user = request.user
    recent_files = UploadedFile.objects.filter(user=user).order_by('-upload_at')
    total_files = UploadedFile.objects.filter(user=user).count()
    
    col_sum = UploadedFile.objects.filter(user=user).aggregate(Sum('column_count'))['column_count__sum']
    total_columns = col_sum if col_sum else 0
    
    total_presets = Preset.objects.filter(user=user).count()
    recent_presets = Preset.objects.filter(user=user).order_by('-created_at')
    
    total_exports = ExportJob.objects.filter(session__user=user, status='COMPLETED').count()

    context = {
        'total_files': total_files,
        'total_columns': total_columns,
        'total_exports': total_exports,
        'total_presets': total_presets,
        'recent_files': recent_files,
        'recent_presets': recent_presets,
    }
    return render(request, 'dashboard.html', context)


@login_required
def workspace_view(request):
    """Main workspace with 3-panel layout."""
    return render(request, 'workspace.html')


def register_view(request):
    """User registration page."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('/')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})
