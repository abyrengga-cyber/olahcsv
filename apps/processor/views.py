import os
import math
import pandas as pd
from django.core.files import File
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from apps.files.models import UploadedFile
from apps.files.utils import detect_encoding, detect_delimiter
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

            df = pd.read_csv(path, sep=delimiter, encoding=encoding)

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

            df = pd.read_csv(path, sep=delimiter, encoding=encoding)

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

            df.to_csv(new_full_path, index=False, sep=delimiter, encoding=encoding)

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
