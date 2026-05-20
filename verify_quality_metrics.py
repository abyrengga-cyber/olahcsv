import os
import sys
import pandas as pd

# Setup path
sys.path.append('d:/proyek3')

from apps.files.utils import parse_file_metadata

# Create a file with 100 rows of complete data, followed by 100 rows with missing values
rows = []
for i in range(100):
    rows.append({'col1': i, 'col2': f'name_{i}', 'col3': i * 1.5})

for i in range(100, 200):
    rows.append({'col1': i, 'col2': None, 'col3': None}) # Missing values here

df = pd.DataFrame(rows)
file_path = 'd:/proyek3/media/test_quality_bug.csv'
os.makedirs(os.path.dirname(file_path), exist_ok=True)
df.to_csv(file_path, index=False)

print(f"Test file created at {file_path}")

# Test parse_file_metadata
result = parse_file_metadata(file_path)

if result['success']:
    quality = result['quality']
    print(f"Complete rows %: {quality['complete_rows_pct']}")
    print(f"Problematic columns: {quality['problematic_cols_count']}")
    
    # Expected: 50% complete rows and 2 problematic columns (col2 and col3)
    if quality['complete_rows_pct'] == 50.0 and quality['problematic_cols_count'] == 2:
        print("Success! Data quality metrics are accurate for larger samples.")
    else:
        print("Failure: Metrics are not as expected.")
else:
    print(f"Failed to parse metadata: {result['error']}")

# Cleanup
# os.remove(file_path)
