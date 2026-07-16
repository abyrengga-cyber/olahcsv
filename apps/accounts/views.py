from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate

from apps.files.models import UploadedFile
from apps.presets.models import Preset
from apps.export.models import ExportJob


@login_required
def dashboard_chart_data(request):
    user = request.user
    uploads = (
        UploadedFile.objects.filter(user=user)
        .annotate(date=TruncDate("upload_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    exports = (
        ExportJob.objects.filter(session__user=user, status="COMPLETED")
        .annotate(date=TruncDate("completed_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    all_dates = sorted(
        set(u["date"] for u in uploads) | set(e["date"] for e in exports if e["date"])
    )
    if not all_dates:
        return JsonResponse({"labels": [], "uploads": [], "exports": []})

    upload_dict = {u["date"]: u["count"] for u in uploads}
    export_dict = {e["date"]: e["count"] for e in exports if e["date"]}

    labels = [d.strftime("%d/%m") for d in all_dates]
    upload_counts = [upload_dict.get(d, 0) for d in all_dates]
    export_counts = [export_dict.get(d, 0) for d in all_dates]

    return JsonResponse(
        {"labels": labels, "uploads": upload_counts, "exports": export_counts}
    )


@login_required
def dashboard(request):
    """Landing page with upload zone, stats, recent files."""
    user = request.user
    recent_files = UploadedFile.objects.filter(user=user).order_by("-upload_at")[:10]
    total_files = UploadedFile.objects.filter(user=user).count()

    col_sum = UploadedFile.objects.filter(user=user).aggregate(Sum("column_count"))[
        "column_count__sum"
    ]
    total_columns = col_sum if col_sum else 0

    total_presets = Preset.objects.filter(user=user).count()
    recent_presets = Preset.objects.filter(user=user).order_by("-created_at")[:10]

    total_exports = ExportJob.objects.filter(
        session__user=user, status="COMPLETED"
    ).count()

    recent_exports = ExportJob.objects.filter(
        session__user=user, status="COMPLETED"
    ).order_by("-completed_at")[:10]
    import os

    for ex in recent_exports:
        if ex.output_file:
            ex.filename = os.path.basename(ex.output_file.name)
        else:
            ex.filename = f"Export_{ex.id}.{ex.format}"

    context = {
        "total_files": total_files,
        "total_columns": total_columns,
        "total_exports": total_exports,
        "total_presets": total_presets,
        "recent_files": recent_files,
        "recent_presets": recent_presets,
        "recent_exports": recent_exports,
    }
    return render(request, "dashboard.html", context)


@login_required
def workspace_view(request):
    """Main workspace with 3-panel layout."""
    return render(request, "workspace.html")


def register_view(request):
    """User registration page."""
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("/")
    else:
        form = UserCreationForm()
    return render(request, "accounts/register.html", {"form": form})
