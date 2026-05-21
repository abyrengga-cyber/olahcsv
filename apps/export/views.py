import os
import io
import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from apps.files.models import UploadedFile
from apps.processor.models import ProcessingSession
from apps.export.models import ExportJob
import pandas as pd
import uuid

class ExportDataView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        file_ids = data.get('file_ids', [])
        export_format = data.get('format', 'csv')
        columns_config = data.get('columns', [])

        # Multi-sheet data
        aggregation_result = data.get('aggregation_result', [])
        aggregation_columns = data.get('aggregation_columns', [])
        comparison_result = data.get('comparison_result', [])
        comparison_columns = data.get('comparison_columns', [])

        # Sheet inclusion flags (default True if data exists)
        include_aggregation = data.get('include_aggregation', True)
        include_comparison = data.get('include_comparison', True)

        if not file_ids:
            return Response({'error': 'No files specified'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_obj = UploadedFile.objects.get(id=file_ids[0])

            df = pd.read_csv(file_obj.file_path.path, sep=file_obj.delimiter, encoding=file_obj.encoding)

            # Select and rename columns if config provided
            if columns_config:
                cols_to_keep = [col['name'] for col in columns_config if col.get('include', True)]
                if cols_to_keep:
                    valid_cols = [c for c in cols_to_keep if c in df.columns]
                    df = df[valid_cols]

                    rename_map = {col['name']: col.get('alias', col['name']) for col in columns_config if col.get('alias') and col['name'] in valid_cols}
                    if rename_map:
                        df = df.rename(columns=rename_map)

            # Create export directory
            export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
            os.makedirs(export_dir, exist_ok=True)

            # Build timestamped filename
            now = timezone.now()
            ts = now.strftime('%Y%m%d_%H%M%S')
            base_name = os.path.splitext(file_obj.original_filename)[0] if file_obj.original_filename else 'Data_Export'
            output_filename = f"{base_name}_{ts}.{export_format}"
            output_path = os.path.join(export_dir, output_filename)
            output_url = f"{settings.MEDIA_URL}exports/{output_filename}"

            if export_format == 'csv':
                df.to_csv(output_path, index=False)

            elif export_format == 'xlsx':
                with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                    # Sheet 1: Data Asli
                    df.to_excel(writer, sheet_name='Data', index=False)

                    # Sheet 2: Agregasi (if available and included)
                    if include_aggregation and aggregation_result and aggregation_columns:
                        agg_df = pd.DataFrame(aggregation_result)
                        valid_agg_cols = [c for c in aggregation_columns if c in agg_df.columns]
                        if valid_agg_cols:
                            agg_df = agg_df[valid_agg_cols]
                        agg_df.to_excel(writer, sheet_name='Agregasi', index=False)

                    # Sheet 3: Perbandingan (if available and included)
                    if include_comparison and comparison_result and comparison_columns:
                        comp_df = pd.DataFrame(comparison_result)
                        valid_comp_cols = [c for c in comparison_columns if c in comp_df.columns]
                        if valid_comp_cols:
                            comp_df = comp_df[valid_comp_cols]
                        comp_df.to_excel(writer, sheet_name='Perbandingan', index=False)

            else:
                return Response({'error': 'Invalid format'}, status=status.HTTP_400_BAD_REQUEST)

            # --- Record export in database for Dashboard history ---
            try:
                session, _ = ProcessingSession.objects.get_or_create(
                    user=request.user,
                    status='ACTIVE',
                    defaults={'configuration': {}}
                )
                session.files.add(file_obj)

                ExportJob.objects.create(
                    session=session,
                    format=export_format,
                    status='COMPLETED',
                    output_file=f"exports/{output_filename}",
                    completed_at=now
                )
            except Exception:
                pass  # Don't fail the export if logging fails

            # Build sheet info for response
            sheets = ['Data']
            if export_format == 'xlsx':
                if include_aggregation and aggregation_result and aggregation_columns:
                    sheets.append('Agregasi')
                if include_comparison and comparison_result and comparison_columns:
                    sheets.append('Perbandingan')

            return Response({
                'url': output_url,
                'filename': output_filename,
                'sheets': sheets
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
