import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from apps.export.models import ExportJob


class Command(BaseCommand):
    help = "Hapus file export dan record yang lebih tua dari N hari"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=7, help="Umur maksimal file export (hari)"
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Simulasi tanpa hapus"
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(days=days)

        old_jobs = ExportJob.objects.filter(created_at__lt=cutoff)
        count = old_jobs.count()
        self.stdout.write(f"Menemukan {count} export lama (> {days} hari)")

        if dry_run:
            self.stdout.write("Dry-run: tidak ada yang dihapus")
            return

        deleted_files = 0
        for job in old_jobs:
            if job.output_file:
                path = os.path.join(settings.MEDIA_ROOT, job.output_file.name)
                if os.path.exists(path):
                    os.remove(path)
                    deleted_files += 1

        old_jobs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Selesai: {count} record + {deleted_files} file dihapus"
            )
        )
