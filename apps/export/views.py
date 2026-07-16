import os
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from apps.files.models import UploadedFile
from apps.files.utils import read_dataframe, apply_filters
from apps.processor.models import ProcessingSession
from apps.export.models import ExportJob
import pandas as pd

logger = logging.getLogger(__name__)


def _sanitize_df(df):
    def _escape(v):
        if isinstance(v, str) and v:
            first = v[0]
            if first in "=+-@\t" or first in "\r\n\0" or ord(first) in (0xFFFE, 0xFEFF):
                return "'" + v
            for ch in ("\r", "\n", "\0"):
                if ch in v:
                    return "'" + v
            for prefix in ("= ", "=	", "=\r", "=\n"):
                if v.startswith(prefix):
                    return "'" + v
        return v

    if hasattr(df, "map"):
        return df.map(_escape)
    return df.applymap(_escape)


ALLOWED_EXPORT_FORMATS = {"csv", "xlsx"}


class ExportDataView(APIView):
    throttle_scope = "heavy"

    def post(self, request, *args, **kwargs):
        data = request.data
        file_ids = data.get("file_ids", [])
        export_format = data.get("format", "csv")

        if export_format not in ALLOWED_EXPORT_FORMATS:
            return Response(
                {
                    "error": f"Format '{export_format}' tidak didukung. Gunakan: {', '.join(sorted(ALLOWED_EXPORT_FORMATS))}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        columns_config = data.get("columns", [])

        # Filter parameters (from preview filter UI)
        export_scope = data.get("export_scope", "all")
        filter_col = data.get("filter_col", "")
        filter_op = data.get("filter_op", "contains")
        filter_query = data.get("filter_query", "")
        filter_col2 = data.get("filter_col2", "")
        filter_op2 = data.get("filter_op2", "contains")
        filter_query2 = data.get("filter_query2", "")
        filter_logic = data.get("filter_logic", "AND")
        filters = data.get("filters", None)

        # Sort parameters (from preview sort UI)
        sort_by = data.get("sort_by", "")
        sort_order = data.get("sort_order", "asc")  # 'asc' or 'desc'

        # Multi-sheet data
        aggregation_result = data.get("aggregation_result", [])
        aggregation_columns = data.get("aggregation_columns", [])
        comparison_result = data.get("comparison_result", [])
        comparison_columns = data.get("comparison_columns", [])

        # Sheet inclusion flags (default True if data exists)
        include_aggregation = data.get("include_aggregation", True)
        include_comparison = data.get("include_comparison", True)

        if not file_ids:
            return Response(
                {"error": "No files specified"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            file_obj = UploadedFile.objects.get(id=file_ids[0], user=request.user)
        except UploadedFile.DoesNotExist:
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )

        output_path = None
        try:
            df = read_dataframe(
                file_obj.file_path.path,
                delimiter=file_obj.delimiter,
                encoding=file_obj.encoding,
            )

            # Apply filter rows if export_scope is 'filtered'
            if export_scope == "filtered":
                df = apply_filters(
                    df,
                    filters,
                    filter_logic,
                    filter_col,
                    filter_query,
                    filter_op,
                    filter_col2,
                    filter_query2,
                    filter_op2,
                )

            # Apply sort if requested (mirrors preview panel sort)
            if sort_by and sort_by in df.columns:
                ascending = sort_order != "desc"
                df = df.sort_values(by=sort_by, ascending=ascending, na_position="last")

            # Select and rename columns if config provided
            if columns_config:
                cols_to_keep = [
                    col["name"] for col in columns_config if col.get("include", True)
                ]
                if cols_to_keep:
                    valid_cols = [c for c in cols_to_keep if c in df.columns]
                    df = df[valid_cols]

                    rename_map = {
                        col["name"]: col.get("alias", col["name"])
                        for col in columns_config
                        if col.get("alias") and col["name"] in valid_cols
                    }
                    if rename_map:
                        df = df.rename(columns=rename_map)

            # Record export in database BEFORE writing file
            now = timezone.now()
            session = ProcessingSession.get_active(request.user)
            session.files.add(file_obj)

            export_job = ExportJob.objects.create(
                session=session,
                format=export_format,
                status="PROCESSING",
                completed_at=now,
            )

            # Create export directory
            export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
            os.makedirs(export_dir, exist_ok=True)

            # Build timestamped filename
            ts = now.strftime("%Y%m%d_%H%M%S")
            base_name = (
                os.path.splitext(file_obj.original_filename)[0]
                if file_obj.original_filename
                else "Data_Export"
            )
            output_filename = f"{base_name}_{ts}.{export_format}"
            output_path = os.path.join(export_dir, output_filename)
            output_url = f"{settings.MEDIA_URL}exports/{output_filename}"

            df = _sanitize_df(df)

            if export_format == "csv":
                df.to_csv(output_path, index=False)

            elif export_format == "xlsx":
                with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                    df.to_excel(writer, sheet_name="Data", index=False)

                    if (
                        include_aggregation
                        and aggregation_result
                        and aggregation_columns
                    ):
                        agg_df = pd.DataFrame(aggregation_result)
                        valid_agg_cols = [
                            c for c in aggregation_columns if c in agg_df.columns
                        ]
                        if valid_agg_cols:
                            agg_df = _sanitize_df(agg_df[valid_agg_cols])
                        agg_df.to_excel(writer, sheet_name="Agregasi", index=False)

                    if include_comparison and comparison_result and comparison_columns:
                        comp_df = pd.DataFrame(comparison_result)
                        valid_comp_cols = [
                            c for c in comparison_columns if c in comp_df.columns
                        ]
                        if valid_comp_cols:
                            comp_df = _sanitize_df(comp_df[valid_comp_cols])
                        comp_df.to_excel(writer, sheet_name="Perbandingan", index=False)

            else:
                if output_path and os.path.exists(output_path):
                    os.remove(output_path)
                return Response(
                    {"error": "Invalid format"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Update ExportJob with output file reference
            export_job.output_file = f"exports/{output_filename}"
            export_job.status = "COMPLETED"
            export_job.save(update_fields=["output_file", "status"])

            sheets = ["Data"]
            if export_format == "xlsx":
                if include_aggregation and aggregation_result and aggregation_columns:
                    sheets.append("Agregasi")
                if include_comparison and comparison_result and comparison_columns:
                    sheets.append("Perbandingan")

            return Response(
                {"url": output_url, "filename": output_filename, "sheets": sheets},
                status=status.HTTP_200_OK,
            )

        except Exception:
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            logger.exception("Export failed")
            return Response(
                {"error": "Export gagal diproses."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
