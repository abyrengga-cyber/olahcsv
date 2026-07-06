import os
import json
import io
import pandas as pd
import chardet
import numpy as np

XLSX_EXTENSIONS = {".xlsx", ".xls"}


def _get_ext(file_path):
    return os.path.splitext(file_path)[1].lower()


def is_xlsx(file_path):
    return _get_ext(file_path) in XLSX_EXTENSIONS


def detect_encoding(file_path):
    if is_xlsx(file_path):
        return None

    with open(file_path, "rb") as f:
        raw_data = f.read(100000)
        result = chardet.detect(raw_data)
        encoding = result["encoding"]

        if not encoding or encoding.lower() == "ascii" or result["confidence"] < 0.5:
            encoding = "utf-8"

        return encoding


def detect_delimiter(file_path, encoding):
    if is_xlsx(file_path):
        return None

    delimiters = [",", ";", "\t", "|"]
    scores = {d: 0 for d in delimiters}

    try:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                lines = [f.readline() for _ in range(5)]
        except (UnicodeDecodeError, TypeError):
            with open(file_path, "r", encoding="latin-1") as f:
                lines = [f.readline() for _ in range(5)]

        for line in lines:
            for d in delimiters:
                scores[d] += line.count(d)

        sorted_delimiters = sorted(
            scores.items(), key=lambda item: item[1], reverse=True
        )
        if sorted_delimiters[0][1] > 0:
            return sorted_delimiters[0][0]
        else:
            return ","

    except Exception:
        return ","


def get_column_values(file_path, column, delimiter=None, encoding=None, max_values=500):
    if is_xlsx(file_path):
        df = pd.read_excel(file_path, engine="openpyxl")
    else:
        if not encoding:
            encoding = detect_encoding(file_path)
        if not delimiter:
            delimiter = detect_delimiter(file_path, encoding)
        try:
            df = pd.read_csv(file_path, sep=delimiter, encoding=encoding)
        except (UnicodeDecodeError, TypeError):
            df = pd.read_csv(file_path, sep=delimiter, encoding="latin-1")

    if column not in df.columns:
        return []
    values = df[column].dropna().astype(str).drop_duplicates().head(max_values).tolist()
    return values


def read_dataframe(file_path, delimiter=None, encoding=None):
    if is_xlsx(file_path):
        return pd.read_excel(file_path, engine="openpyxl")
    if not encoding:
        encoding = detect_encoding(file_path)
    if not delimiter:
        delimiter = detect_delimiter(file_path, encoding)
    return pd.read_csv(file_path, sep=delimiter, encoding=encoding)


def apply_filter_mask(df, col, op, query):
    if col not in df.columns or not query:
        return None
    if op in ("gt", "gte", "lt", "lte", "eq", "neq"):
        try:
            val = float(query)
        except (ValueError, TypeError):
            if op in ("eq", "neq"):
                return df[col].astype(str).str.strip() == query.strip()
            return None
        numeric_col = pd.to_numeric(df[col], errors="coerce")
        if op == "gt":
            return numeric_col > val
        elif op == "gte":
            return numeric_col >= val
        elif op == "lt":
            return numeric_col < val
        elif op == "lte":
            return numeric_col <= val
        elif op == "eq":
            return numeric_col == val
        elif op == "neq":
            return numeric_col != val
    elif op == "contains":
        return df[col].astype(str).str.contains(query, na=False, case=False)
    elif op == "startswith":
        return df[col].astype(str).str.startswith(query, na=False)
    return None


def parse_file_metadata(
    file_path,
    delimiter=None,
    encoding=None,
    page=1,
    page_size=20,
    sort_by=None,
    sort_order="asc",
    filter_col=None,
    filter_query=None,
    filter_op="contains",
    filter_col2=None,
    filter_op2="contains",
    filter_query2=None,
    filter_logic="AND",
    filters=None,
):
    if not encoding or (encoding and encoding.lower() == "ascii"):
        encoding = detect_encoding(file_path)

    if not delimiter:
        delimiter = detect_delimiter(file_path, encoding)

    try:
        if is_xlsx(file_path):
            df_full = read_dataframe(file_path)
            row_count = len(df_full)
            df_sample = df_full.head(1000).copy()
        else:
            with open(file_path, "rb") as f:
                total_raw_rows = sum(1 for _ in f)
            row_count = total_raw_rows - 1 if total_raw_rows > 0 else 0

            df_sample = pd.read_csv(
                file_path, sep=delimiter, encoding=encoding, nrows=1000
            )

            try:
                df_full = pd.read_csv(file_path, sep=delimiter, encoding=encoding)
            except pd.errors.EmptyDataError:
                df_full = pd.DataFrame(columns=df_sample.columns)

        if filters:
            masks = []
            for f in filters:
                col = f.get("col", "")
                op = f.get("op", "contains")
                query = f.get("query", "")
                m = apply_filter_mask(df_full, col, op, query)
                if m is not None:
                    masks.append(m)
            if masks:
                combined = masks[0]
                for m in masks[1:]:
                    if filter_logic == "OR":
                        combined = combined | m
                    else:
                        combined = combined & m
                df_full = df_full[combined]
        else:
            mask1 = apply_filter_mask(
                df_full, filter_col, filter_op or "contains", filter_query
            )
            mask2 = apply_filter_mask(
                df_full, filter_col2, filter_op2 or "contains", filter_query2
            )

            if mask1 is not None and mask2 is not None:
                if filter_logic == "OR":
                    df_full = df_full[mask1 | mask2]
                else:
                    df_full = df_full[mask1 & mask2]
            elif mask1 is not None:
                df_full = df_full[mask1]
            elif mask2 is not None:
                df_full = df_full[mask2]

        row_count = len(df_full)

        if sort_by and sort_by in df_full.columns:
            ascending = sort_order.lower() != "desc"
            df_full = df_full.sort_values(by=sort_by, ascending=ascending)

        skip_rows = (page - 1) * page_size
        df_page = df_full.iloc[skip_rows : skip_rows + page_size].reset_index(drop=True)

        columns_info = []
        problematic_cols_count = 0
        for col in df_sample.columns:
            dtype = str(df_sample[col].dtype)

            if "int" in dtype or "float" in dtype:
                col_type = "num"
            elif "datetime" in dtype:
                col_type = "date"
            else:
                col_name_lower = str(col).lower()
                if any(
                    k in col_name_lower
                    for k in ["date", "time", "tgl", "jam", "timestamp"]
                ):
                    col_type = "date"
                else:
                    col_type = "str"

            missing_pct = round(df_sample[col].isnull().mean() * 100, 2)
            if missing_pct > 0:
                problematic_cols_count += 1

            columns_info.append(
                {"name": col, "type": col_type, "missing_pct": missing_pct}
            )

        total_cells = df_sample.size
        filled_cells = int(df_sample.count().sum())
        complete_rows_pct = (
            round((filled_cells / total_cells) * 100, 1) if total_cells > 0 else 100.0
        )

        preview_data = df_page.fillna("").to_dict(orient="records")

        return {
            "success": True,
            "delimiter": delimiter,
            "encoding": encoding,
            "row_count": row_count,
            "column_count": len(df_sample.columns),
            "columns": columns_info,
            "preview": preview_data,
            "page": page,
            "page_size": page_size,
            "quality": {
                "complete_rows_pct": complete_rows_pct,
                "problematic_cols_count": problematic_cols_count,
            },
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
