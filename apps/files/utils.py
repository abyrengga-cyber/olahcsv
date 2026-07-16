import os
import logging
import pandas as pd
import chardet
import filetype

logger = logging.getLogger(__name__)

XLSX_EXTENSIONS = {".xlsx", ".xls"}
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def sanitize_filename(name):
    name = os.path.basename(name)
    name = name.replace("\x00", "")
    return name[:255]


def validate_file_mime(file_obj):
    filename = getattr(file_obj, "name", "") or ""
    ext = os.path.splitext(filename)[1].lower()

    file_obj.seek(0)
    magic_bytes = file_obj.read(2048)
    file_obj.seek(0)

    kind = filetype.guess(magic_bytes)

    if kind and kind.extension in ("xlsx", "xls"):
        detected_ext = f".{kind.extension}"
        if ext and ext != detected_ext:
            return (
                False,
                f"Extension '{ext}' tidak cocok dengan isi file (terdeteksi sebagai {detected_ext}).",
            )
        return True, ""

    if ext == ".csv" or (not ext and b"\x00" not in magic_bytes):
        if b"\x00" in magic_bytes:
            return False, "File tidak valid (mengandung binary data)."
        return True, ""

    return (
        False,
        f"Tipe file '{ext}' tidak diizinkan. Hanya {', '.join(ALLOWED_EXTENSIONS)} yang diperbolehkan.",
    )


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
        if column not in df.columns:
            return []
        values = (
            df[column].dropna().astype(str).drop_duplicates().head(max_values).tolist()
        )
        return values

    if not encoding:
        encoding = detect_encoding(file_path)
    if not delimiter:
        delimiter = detect_delimiter(file_path, encoding)

    seen = set()
    values = []
    try:
        for chunk in pd.read_csv(
            file_path,
            sep=delimiter,
            encoding=encoding,
            usecols=[column],
            chunksize=10000,
        ):
            if column not in chunk.columns:
                continue
            for v in chunk[column].dropna().astype(str).unique():
                if v not in seen and v:
                    seen.add(v)
                    values.append(v)
                    if len(values) >= max_values:
                        return values
    except (UnicodeDecodeError, TypeError):
        for chunk in pd.read_csv(
            file_path,
            sep=delimiter,
            encoding="latin-1",
            usecols=[column],
            chunksize=10000,
        ):
            if column not in chunk.columns:
                continue
            for v in chunk[column].dropna().astype(str).unique():
                if v not in seen and v:
                    seen.add(v)
                    values.append(v)
                    if len(values) >= max_values:
                        return values
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


def _resolve_encoding_and_delimiter(file_path, encoding, delimiter):
    if not encoding or (encoding and encoding.lower() == "ascii"):
        encoding = detect_encoding(file_path)
    if not delimiter:
        delimiter = detect_delimiter(file_path, encoding)
    return encoding, delimiter


def _load_dataframe(file_path, encoding, delimiter):
    loaded_all_rows = True
    if is_xlsx(file_path):
        df_full = read_dataframe(file_path)
        row_count = len(df_full)
        df_sample = df_full.head(1000).copy()
        return df_full, df_sample, row_count, loaded_all_rows

    df_sample = pd.read_csv(file_path, sep=delimiter, encoding=encoding, nrows=1000)
    try:
        file_size = os.path.getsize(file_path)
        if file_size > 200 * 1024 * 1024:
            loaded_all_rows = False
            with open(file_path, "rb") as f:
                row_count = sum(1 for _ in f) - 1
            df_full = pd.read_csv(
                file_path, sep=delimiter, encoding=encoding, nrows=10000
            )
        else:
            df_full = pd.read_csv(file_path, sep=delimiter, encoding=encoding)
            row_count = len(df_full)
    except pd.errors.EmptyDataError:
        df_full = pd.DataFrame(columns=df_sample.columns)
        row_count = 0
    return df_full, df_sample, row_count, loaded_all_rows


def _apply_filters(
    df,
    filters,
    filter_logic,
    filter_col=None,
    filter_query=None,
    filter_op="contains",
    filter_col2=None,
    filter_op2="contains",
    filter_query2=None,
):
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
            return df[combined]
        return df

    mask1 = apply_filter_mask(df, filter_col, filter_op or "contains", filter_query)
    mask2 = apply_filter_mask(df, filter_col2, filter_op2 or "contains", filter_query2)

    if mask1 is not None and mask2 is not None:
        if filter_logic == "OR":
            return df[mask1 | mask2]
        return df[mask1 & mask2]
    if mask1 is not None:
        return df[mask1]
    if mask2 is not None:
        return df[mask2]
    return df


def _apply_sort(df, sort_by, sort_order):
    if sort_by and sort_by in df.columns:
        ascending = sort_order.lower() != "desc"
        return df.sort_values(by=sort_by, ascending=ascending)
    return df


def _paginate(df, page, page_size):
    skip_rows = (page - 1) * page_size
    return df.iloc[skip_rows : skip_rows + page_size].reset_index(drop=True)


def _build_columns_info(df_sample):
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
                k in col_name_lower for k in ["date", "time", "tgl", "jam", "timestamp"]
            ):
                col_type = "date"
            else:
                col_type = "str"

        missing_pct = round(df_sample[col].isnull().mean() * 100, 2)
        if missing_pct > 0:
            problematic_cols_count += 1
        columns_info.append({"name": col, "type": col_type, "missing_pct": missing_pct})
    return columns_info, problematic_cols_count


def _build_quality(df_sample):
    total_cells = df_sample.size
    filled_cells = int(df_sample.count().sum())
    complete_rows_pct = (
        round((filled_cells / total_cells) * 100, 1) if total_cells > 0 else 100.0
    )
    return {"complete_rows_pct": complete_rows_pct}


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
    try:
        encoding, delimiter = _resolve_encoding_and_delimiter(
            file_path, encoding, delimiter
        )
        df_full, df_sample, row_count, loaded_all_rows = _load_dataframe(
            file_path, encoding, delimiter
        )
        df_full = _apply_filters(
            df_full,
            filters,
            filter_logic,
            filter_col,
            filter_query,
            filter_op,
            filter_col2,
            filter_op2,
            filter_query2,
        )

        if loaded_all_rows:
            row_count = len(df_full)

        df_full = _apply_sort(df_full, sort_by, sort_order)
        df_page = _paginate(df_full, page, page_size)
        columns_info, problematic_cols_count = _build_columns_info(df_sample)
        quality = _build_quality(df_sample)
        quality["problematic_cols_count"] = problematic_cols_count
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
            "quality": quality,
        }

    except Exception:
        logger.exception("parse_file_metadata failed")
        return {"success": False, "error": "Gagal memproses file."}
