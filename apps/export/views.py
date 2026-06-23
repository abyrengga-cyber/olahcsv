import os
import io
import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from apps.files.models import UploadedFile
from apps.files.utils import read_dataframe, _apply_filter
from apps.processor.models import ProcessingSession
from apps.export.models import ExportJob
import pandas as pd
import uuid


class ExportDataView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data
        file_ids = data.get("file_ids", [])
        export_format = data.get("format", "csv")
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
            file_obj = UploadedFile.objects.get(id=file_ids[0])

            df = read_dataframe(
                file_obj.file_path.path,
                delimiter=file_obj.delimiter,
                encoding=file_obj.encoding,
            )

            # Apply filter rows if export_scope is 'filtered'
            if export_scope == "filtered":
                if filters:
                    masks = []
                    for f in filters:
                        col = f.get("col", "")
                        op = f.get("op", "contains")
                        query = f.get("query", "")
                        m = _apply_filter(df, col, op, query)
                        masks.append(m)
                    active_masks = [m for m in masks if m is not df]
                    if active_masks:
                        combined = active_masks[0]
                        for m in active_masks[1:]:
                            combined = (
                                combined | m if filter_logic == "OR" else combined & m
                            )
                        df = df[combined]
                else:
                    mask1 = _apply_filter(df, filter_col, filter_op, filter_query)
                    mask2 = _apply_filter(df, filter_col2, filter_op2, filter_query2)
                    if mask1 is not df and mask2 is not df:
                        df = (
                            df[mask1 & mask2]
                            if filter_logic == "AND"
                            else df[mask1 | mask2]
                        )
                    elif mask1 is not df:
                        df = mask1
                    elif mask2 is not df:
                        df = mask2

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

            # Create export directory
            export_dir = os.path.join(settings.MEDIA_ROOT, "exports")
            os.makedirs(export_dir, exist_ok=True)

            # Build timestamped filename
            now = timezone.now()
            ts = now.strftime("%Y%m%d_%H%M%S")
            base_name = (
                os.path.splitext(file_obj.original_filename)[0]
                if file_obj.original_filename
                else "Data_Export"
            )
            output_filename = f"{base_name}_{ts}.{export_format}"
            output_path = os.path.join(export_dir, output_filename)
            output_url = f"{settings.MEDIA_URL}exports/{output_filename}"

            if export_format == "csv":
                df.to_csv(output_path, index=False)

            elif export_format == "xlsx":
                with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                    # Sheet 1: Data Asli
                    df.to_excel(writer, sheet_name="Data", index=False)

                    # Sheet 2: Agregasi (if available and included)
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
                            agg_df = agg_df[valid_agg_cols]
                        agg_df.to_excel(writer, sheet_name="Agregasi", index=False)

                    # Sheet 3: Perbandingan (if available and included)
                    if include_comparison and comparison_result and comparison_columns:
                        comp_df = pd.DataFrame(comparison_result)
                        valid_comp_cols = [
                            c for c in comparison_columns if c in comp_df.columns
                        ]
                        if valid_comp_cols:
                            comp_df = comp_df[valid_comp_cols]
                        comp_df.to_excel(writer, sheet_name="Perbandingan", index=False)

            else:
                return Response(
                    {"error": "Invalid format"}, status=status.HTTP_400_BAD_REQUEST
                )

            # --- Record export in database for Dashboard history ---
            try:
                session, _ = ProcessingSession.objects.get_or_create(
                    user=request.user, status="ACTIVE", defaults={"configuration": {}}
                )
                session.files.add(file_obj)

                ExportJob.objects.create(
                    session=session,
                    format=export_format,
                    status="COMPLETED",
                    output_file=f"exports/{output_filename}",
                    completed_at=now,
                )
            except Exception:
                pass  # Don't fail the export if logging fails

            # Build sheet info for response
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

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
