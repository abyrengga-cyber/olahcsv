from django.db import models
from apps.processor.models import ProcessingSession

class ExportJob(models.Model):
    session = models.ForeignKey(ProcessingSession, on_delete=models.CASCADE, related_name='exports')
    format = models.CharField(max_length=10) # csv, xlsx
    status = models.CharField(max_length=50, default='PENDING') # PENDING, PROCESSING, COMPLETED, ERROR
    output_file = models.FileField(upload_to='exports/%Y/%m/%d/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"ExportJob {self.id} ({self.format}) - {self.status}"
