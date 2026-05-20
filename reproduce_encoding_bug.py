import os
import sys
import pandas as pd
import chardet

# Setup path
sys.path.append('d:/proyek3')

from apps.files.utils import parse_file_metadata, detect_encoding

# 1. Create a problematic file
# 150KB of ASCII data, then a non-ASCII character (0xc3)
content = "id,name,value\n"
for i in range(10000):
    content += f"{i},row_{i},value_{i}\n"

# Ensure content is > 100KB
while len(content) < 150000:
    content += "99999,padding,padding_value\n"

# Add non-ASCII character at the end
# 0xc3 is 195 in decimal
content_bytes = content.encode('ascii') + bytes([195]) + " extra data".encode('ascii')

file_path = 'd:/proyek3/media/test_encoding_bug.csv'
os.makedirs(os.path.dirname(file_path), exist_ok=True)
with open(file_path, 'wb') as f:
    f.write(content_bytes)

print(f"Test file created at {file_path}, size: {os.path.getsize(file_path)} bytes")

# 2. Test detect_encoding
encoding = detect_encoding(file_path)
print(f"Detected encoding: {encoding}")

# 3. Test parse_file_metadata
try:
    result = parse_file_metadata(file_path)
    if result['success']:
        print("Success! metadata parsed correctly.")
        print(f"Encoding used: {result['encoding']}")
        print(f"Problematic columns: {result['quality']['problematic_cols_count']}")
    else:
        print(f"Failed: {result['error']}")
except Exception as e:
    print(f"Exception raised: {e}")

# Cleanup
# os.remove(file_path)
