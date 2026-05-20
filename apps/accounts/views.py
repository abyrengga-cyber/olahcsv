from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required


def dashboard(request):
    """Landing page with upload zone, stats, recent files."""
    return render(request, 'dashboard.html')


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
