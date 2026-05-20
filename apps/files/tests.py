import os
import tempfile
import pandas as pd
from django.test import TestCase
from apps.files.utils import detect_encoding, detect_delimiter, parse_file_metadata

class FilesUtilsTest(TestCase):
    def setUp(self):
        # Create a temporary CSV file
        self.temp_csv = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', encoding='utf-8')
        self.temp_csv.write("id,name,age\n1,Alice,30\n2,Bob,25\n3,Charlie,35")
        self.temp_csv.close()
        
        # Create a temporary TSV file
        self.temp_tsv = tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8')
        self.temp_tsv.write("id\tname\tage\n1\tAlice\t30\n2\tBob\t25\n3\tCharlie\t35")
        self.temp_tsv.close()

    def tearDown(self):
        os.unlink(self.temp_csv.name)
        os.unlink(self.temp_tsv.name)

    def test_detect_encoding(self):
        enc = detect_encoding(self.temp_csv.name)
        self.assertIn(enc.lower(), ['ascii', 'utf-8'])

    def test_detect_delimiter(self):
        self.assertEqual(detect_delimiter(self.temp_csv.name, 'utf-8'), ',')
        self.assertEqual(detect_delimiter(self.temp_tsv.name, 'utf-8'), '\t')

    def test_parse_file_metadata(self):
        metadata = parse_file_metadata(self.temp_csv.name)
        self.assertTrue(metadata['success'])
        self.assertEqual(metadata['delimiter'], ',')
        self.assertEqual(metadata['row_count'], 3)
        self.assertEqual(metadata['column_count'], 3)
        
        columns = [c['name'] for c in metadata['columns']]
        self.assertEqual(columns, ['id', 'name', 'age'])
        
        # Check preview
        self.assertEqual(len(metadata['preview']), 3)
        self.assertEqual(metadata['preview'][0]['name'], 'Alice')
