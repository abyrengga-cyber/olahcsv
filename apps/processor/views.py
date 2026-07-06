import os
import io
import math
import pandas as pd
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from apps.files.models import UploadedFile
from apps.files.utils import (
    detect_encoding,
    detect_delimiter,
    read_dataframe,
    apply_filter_mask,
)
from apps.processor.models import ProcessingSession


class AggregationView(APIView):
    def post(self, request):
        file_id = request.data.get("file_id")
        cols = request.data.get("columns", [])
        types = request.data.get("types", [])
        group_by = request.data.get("group_by")

        if not file_id or not cols or not types:
            return Response(
                {"error": "Missing parameters"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)
            session, _ = ProcessingSession.objects.get_or_create(
                user=request.user, status="ACTIVE", defaults={"configuration": {}}
            )
            session.files.add(uploaded_file)

            path = uploaded_file.file_path.path
            encoding = uploaded_file.encoding or detect_encoding(path)
            delimiter = uploaded_file.delimiter or detect_delimiter(path, encoding)

            df = read_dataframe(path, delimiter=delimiter, encoding=encoding)

            # Map frontend types to pandas agg functions
            agg_map = {
                "SUM": "sum",
                "AVG": "mean",
                "MIN": "min",
                "MAX": "max",
                "COUNT": "count",
            }

            # Numeric columns list for safe execution
            import numpy as np

            numeric_cols = set(df.select_dtypes(include=[np.number]).columns)

            if group_by:
                agg_dict = {}
                for c in cols:
                    c_funcs = []
                    for t in types:
                        if t not in agg_map:
                            continue
                        func = agg_map[t]
                        # prevent math ops on non-numeric to avoid crashes (e.g string concat)
                        if func in ["sum", "mean"] and c not in numeric_cols:
                            continue
                        c_funcs.append(func)
                    if c_funcs:
                        agg_dict[c] = c_funcs

                if not agg_dict:
                    return Response(
                        {
                            "error": "Tidak ada kombinasi kolom dan jenis agregasi yang valid. (Contoh: SUM hanya untuk angka)"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                result_df = df.groupby(group_by).agg(agg_dict)
                # Flatten multi-index columns if they exist
                if isinstance(result_df.columns, pd.MultiIndex):
                    result_df.columns = [
                        f"{col}_{func}" for col, func in result_df.columns
                    ]
                result_df = result_df.reset_index()
            else:
                # If no group_by, generate a single row with 'col_type' headers
                stats = {}
                for col in cols:
                    for t in types:
                        f = agg_map.get(t)
                        if f:
                            if f in ["sum", "mean"] and col not in numeric_cols:
                                continue
                            val = df[col].agg(f)
                            # Handle potential numpy types for JSON serialization
                            if hasattr(val, "item"):
                                val = val.item()
                            stats[f"{col}_{t}"] = val
                if not stats:
                    return Response(
                        {
                            "error": "Tidak ada perhitungan yang berhasil. Pastikan Anda memilih kolom angka untuk operasi matematika."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                result_df = pd.DataFrame([stats])

            return Response(
                {
                    "success": True,
                    "data": result_df.fillna("").to_dict(orient="records"),
                    "columns": list(result_df.columns),
                }
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ComparisonView(APIView):
    def post(self, request):
        file_id = request.data.get("file_id")
        col_a = request.data.get("col_a")
        col_b = request.data.get("col_b")
        calc_type = request.data.get("calc_type")
        result_name = request.data.get("result_name", "result")

        if not all([file_id, col_a, col_b, calc_type]):
            return Response(
                {"error": "Missing parameters"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)

            session, _ = ProcessingSession.objects.get_or_create(
                user=request.user, status="ACTIVE", defaults={"configuration": {}}
            )
            session.files.add(uploaded_file)

            path = uploaded_file.file_path.path
            encoding = uploaded_file.encoding or detect_encoding(path)
            delimiter = uploaded_file.delimiter or detect_delimiter(path, encoding)

            df = read_dataframe(path, delimiter=delimiter, encoding=encoding)

            if calc_type == "pct_diff":
                df[result_name] = ((df[col_a] - df[col_b]) / df[col_b]) * 100
            elif calc_type == "ratio":
                df[result_name] = (df[col_a] / df[col_b]) * 100
            elif calc_type == "pct_contrib":
                df[result_name] = (df[col_a] / df[col_a].sum()) * 100
            else:
                return Response(
                    {"error": "Invalid calculation type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Replace inf/-inf/NaN with None to allow JSON serialization
            df[result_name] = df[result_name].replace(
                [float("inf"), float("-inf")], None
            )
            df[result_name] = df[result_name].where(df[result_name].notna(), None)

            # Build comparison-only DataFrame for preview (colA, colB, result)
            compare_cols = [col_a, col_b, result_name]
            compare_df = df[compare_cols].copy()

            # Prepare serializable preview data
            preview_data = compare_df.head(100).fillna("").to_dict(orient="records")
            # Sanitize numeric values for JSON
            for row in preview_data:
                for k, v in row.items():
                    if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
                        row[k] = None

            # Save modified file to temp path
            new_filename = f"processed_{uploaded_file.original_filename}"
            new_dir = os.path.join(settings.MEDIA_ROOT, "uploads", "processed")
            os.makedirs(new_dir, exist_ok=True)
            new_full_path = os.path.join(new_dir, new_filename)

            df.to_csv(
                new_full_path,
                index=False,
                sep=delimiter or ",",
                encoding=encoding or "utf-8",
            )

            # Create new UploadedFile record using Django file wrapper
            with open(new_full_path, "rb") as f:
                new_file = UploadedFile(
                    user=uploaded_file.user,
                    original_filename=new_filename,
                    file_size=os.path.getsize(new_full_path),
                    delimiter=delimiter,
                    encoding=encoding,
                    row_count=len(df),
                    column_count=len(df.columns),
                    status="READY",
                )
                new_file.file_path.save(
                    os.path.join("uploads", "processed", new_filename),
                    File(f),
                    save=True,
                )

            return Response(
                {
                    "success": True,
                    "new_file_id": new_file.id,
                    "message": f"Berhasil membuat kolom baru: {result_name}",
                    "data": preview_data,
                    "columns": compare_cols,
                }
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DateTimeView(APIView):
    def post(self, request):
        file_id = request.data.get("file_id")
        date_col = request.data.get("dateCol", "")
        time_col = request.data.get("timeCol", "")
        output_format = request.data.get("format", "YYYY-MM-DD HH:MM:SS")
        drop_original = request.data.get("dropOriginal", True)

        if not file_id:
            return Response(
                {"error": "Missing file_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)

            session, _ = ProcessingSession.objects.get_or_create(
                user=request.user, status="ACTIVE", defaults={"configuration": {}}
            )
            session.files.add(uploaded_file)

            path = uploaded_file.file_path.path
            encoding = uploaded_file.encoding or detect_encoding(path)
            delimiter = uploaded_file.delimiter or detect_delimiter(path, encoding)

            df = read_dataframe(path, delimiter=delimiter, encoding=encoding)

            result_col = "datetime_normalized"
            originals = []

            if date_col and date_col in df.columns:
                originals.append(date_col)
                parsed_date = pd.to_datetime(df[date_col], errors="coerce")
                if time_col and time_col in df.columns:
                    originals.append(time_col)
                    parsed_time = pd.to_datetime(df[time_col], errors="coerce")
                    date_str = parsed_date.dt.strftime("%Y-%m-%d")
                    safe_time = parsed_time.fillna(pd.Timestamp("1970-01-01 00:00:00"))
                    time_str = safe_time.dt.strftime("%H:%M:%S")
                    time_str = time_str.where(parsed_time.notna(), "00:00:00")
                    df[result_col] = pd.to_datetime(
                        date_str + " " + time_str,
                        errors="coerce",
                    )
                else:
                    df[result_col] = parsed_date
            else:
                auto_col = None
                sample = df.head(100)
                for col in df.columns:
                    try:
                        parsed = pd.to_datetime(sample[col], errors="coerce")
                        if parsed.notna().sum() > len(sample) * 0.5:
                            auto_col = col
                            break
                    except Exception:
                        continue
                if auto_col:
                    originals.append(auto_col)
                    df[result_col] = pd.to_datetime(df[auto_col], errors="coerce")
                else:
                    return Response(
                        {
                            "error": "Tidak dapat mendeteksi kolom tanggal/waktu secara otomatis."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if output_format == "YYYY-MM-DD HH:MM:SS":
                df[result_col] = df[result_col].dt.strftime("%Y-%m-%d %H:%M:%S")
            elif output_format == "DD/MM/YYYY HH:MM:SS":
                df[result_col] = df[result_col].dt.strftime("%d/%m/%Y %H:%M:%S")
            elif output_format == "ISO 8601":
                df[result_col] = df[result_col].dt.strftime("%Y-%m-%dT%H:%M:%S")
            elif output_format == "Unix Timestamp":
                df[result_col] = df[result_col].astype("int64") // 10**9

            if drop_original:
                keep = [c for c in df.columns if c not in originals]
                if result_col not in keep:
                    keep.append(result_col)
                df = df[keep]

            base = uploaded_file.original_filename
            if base.startswith("processed_"):
                base = base[10:]
            new_filename = f"processed_{base}"
            buf = io.BytesIO()
            df.to_csv(
                buf,
                index=False,
                sep=delimiter or ",",
                encoding=encoding or "utf-8",
            )
            csv_bytes = buf.getvalue()

            new_file = UploadedFile(
                user=uploaded_file.user,
                original_filename=new_filename,
                file_size=len(csv_bytes),
                delimiter=delimiter,
                encoding=encoding,
                row_count=len(df),
                column_count=len(df.columns),
                status="READY",
            )
            new_file.file_path.save(
                os.path.join("uploads", "processed", new_filename),
                ContentFile(csv_bytes),
                save=True,
            )

            return Response(
                {
                    "success": True,
                    "new_file_id": new_file.id,
                    "message": "Normalisasi waktu berhasil!",
                }
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ChartDataView(APIView):
    def post(self, request):
        file_id = request.data.get("file_id")
        x_col = request.data.get("x_col")
        y_col = request.data.get("y_col")
        max_points = int(request.data.get("max_points", 1000))
        filters = request.data.get("filters", [])
        filter_logic = request.data.get("filter_logic", "AND")

        if not all([file_id, x_col, y_col]):
            return Response(
                {"error": "Missing parameters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)
            path = uploaded_file.file_path.path
            encoding = uploaded_file.encoding or detect_encoding(path)
            delimiter = uploaded_file.delimiter or detect_delimiter(path, encoding)

            df = read_dataframe(path, delimiter=delimiter, encoding=encoding)

            if filters:
                masks = []
                for f in filters:
                    col = f.get("col", "")
                    op = f.get("op", "contains")
                    query = f.get("query", "")
                    m = apply_filter_mask(df, col, op, query)
                    if m is not None:
                        masks.append(m)
                if masks:
                    combined = masks[0]
                    for m in masks[1:]:
                        if filter_logic == "OR":
                            combined = combined | m
                        else:
                            combined = combined & m
                    df = df[combined]

            if x_col not in df.columns or y_col not in df.columns:
                return Response(
                    {"error": "Column not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            df_subset = df.head(max_points)

            x_vals = df_subset[x_col].tolist()
            y_vals = pd.to_numeric(df_subset[y_col], errors="coerce").tolist()
            data = [
                {"x": None if pd.isna(x) else str(x), "y": None if pd.isna(y) else y}
                for x, y in zip(x_vals, y_vals)
            ]

            return Response(
                {
                    "success": True,
                    "data": data,
                    "total_rows": len(df),
                }
            )

        except Exception as e:
            import traceback

            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
