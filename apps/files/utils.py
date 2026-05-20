import os
import io
import pandas as pd
import chardet
import numpy as np

def detect_encoding(file_path):
    """Detect the encoding of a file using chardet on the first chunk."""
    with open(file_path, 'rb') as f:
        # Read a chunk to guess encoding (usually 100KB is enough)
        raw_data = f.read(100000)
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        
        # ASCII is a subset of UTF-8. If it's ASCII, it might have 
        # non-ASCII characters later in the file. UTF-8 is safer.
        if not encoding or encoding.lower() == 'ascii' or result['confidence'] < 0.5:
            encoding = 'utf-8'
            
        return encoding

def detect_delimiter(file_path, encoding):
    """Attempt to detect the delimiter of a CSV/TXT file."""
    delimiters = [',', ';', '\t', '|']
    scores = {d: 0 for d in delimiters}
    
    try:
        # Try primary encoding
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = [f.readline() for _ in range(5)]
        except (UnicodeDecodeError, TypeError):
            # Fallback to latin-1 if encoding fails (latin-1 never fails to decode bytes)
            with open(file_path, 'r', encoding='latin-1') as f:
                lines = [f.readline() for _ in range(5)]
            
        for line in lines:
            for d in delimiters:
                scores[d] += line.count(d)
                
        # The delimiter with the most occurrences across the first 5 lines is likely the correct one
        sorted_delimiters = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if sorted_delimiters[0][1] > 0:
            return sorted_delimiters[0][0]
        else:
            return ',' # Default to comma if no delimiters found
            
    except Exception:
        return ','

def parse_file_metadata(file_path, delimiter=None, encoding=None, page=1, page_size=20):
    """
    Parse a file and return its metadata: length, columns, types, missing data percentages,
    and a preview of the requested page of rows.
    """
    if not encoding or encoding.lower() == 'ascii':
        encoding = detect_encoding(file_path)
        
    if not delimiter:
        delimiter = detect_delimiter(file_path, encoding)
        
    try:
        # Calculate row count using a fast binary method
        with open(file_path, 'rb') as f:
            total_raw_rows = sum(1 for _ in f)
        
        row_count = total_raw_rows - 1 if total_raw_rows > 0 else 0 # subtract header

        # Read specific rows based on pagination
        skip_rows = (page - 1) * page_size
        
        # Determine column metadata using a larger sample (e.g., 1000 rows) for better quality stats
        df_sample = pd.read_csv(file_path, sep=delimiter, encoding=encoding, nrows=1000)
        
        # Read the actual page data
        # names=df_sample.columns to ensure consistency if skip_rows skips header
        # header=0 if skip_rows=0 else None
        try:
            df_page = pd.read_csv(
                file_path, 
                sep=delimiter, 
                encoding=encoding, 
                skiprows=skip_rows + 1 if skip_rows > 0 else 0,
                nrows=page_size,
                header=0 if skip_rows == 0 else None,
                names=df_sample.columns if skip_rows > 0 else None
            )
        except pd.errors.EmptyDataError:
            df_page = pd.DataFrame(columns=df_sample.columns)
        
        # Determine column metadata
        columns_info = []
        problematic_cols_count = 0
        for col in df_sample.columns:
            dtype = str(df_sample[col].dtype)
            
            # Simple type mapping
            if 'int' in dtype or 'float' in dtype:
                col_type = 'num'
            elif 'datetime' in dtype:
                col_type = 'date'
            else:
                col_name_lower = str(col).lower()
                if any(k in col_name_lower for k in ['date', 'time', 'tgl', 'jam', 'timestamp']):
                    col_type = 'date'
                else:
                    col_type = 'str'
            
            missing_pct = round(df_sample[col].isnull().mean() * 100, 2)
            if missing_pct > 0:
                problematic_cols_count += 1
                
            columns_info.append({
                'name': col,
                'type': col_type,
                'missing_pct': missing_pct
            })
            
        # Calculate complete rows percentage (based on sample for performance)
        complete_rows_count = df_sample.dropna().shape[0]
        complete_rows_pct = round((complete_rows_count / len(df_sample)) * 100, 1) if len(df_sample) > 0 else 100.0
            
        # Get preview data for current page
        preview_data = df_page.fillna('').to_dict(orient='records')
        
        return {
            'success': True,
            'delimiter': delimiter,
            'encoding': encoding,
            'row_count': row_count,
            'column_count': len(df_sample.columns),
            'columns': columns_info,
            'preview': preview_data,
            'page': page,
            'page_size': page_size,
            'quality': {
                'complete_rows_pct': complete_rows_pct,
                'problematic_cols_count': problematic_cols_count
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
