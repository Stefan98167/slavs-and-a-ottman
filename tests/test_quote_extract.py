import io
import json
import tempfile
import unittest
from pathlib import Path

from arena_kit.quote_extract import extract


class QuoteExtractTests(unittest.TestCase):
    def test_runtime_uploads_and_json(self):
        rows = extract([io.StringIO('Part;Unit Price;Currency\n001;17,47;EUR\n'),
                        io.BytesIO(b'\xef\xbb\xbfdescription,qty\n"Adapter, HI",10\n')])
        self.assertEqual(rows[0]["Information"]["Part"], "001")
        self.assertEqual(rows[0]["Information"]["Unit Price"], "17,47")
        self.assertEqual(rows[0]["Priority (Argument wise)"], 1)
        self.assertEqual(rows[1]["Priority (Argument wise)"], 2)
        self.assertEqual(json.loads(json.dumps(rows)), rows)

    def test_path_and_multiline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'quote.csv'
            path.write_text('description,note\nHI,"line one\nline two"\n')
            row = extract(path)[0]
            self.assertEqual(row["Source"], f"{path}:2-3")
            self.assertEqual(row["Information"]["note"], "line one\nline two")

    def test_unknown_columns_empty_and_single_column(self):
        self.assertEqual(extract(io.StringIO('')), [])
        row = extract(io.StringIO('custom\nvalue\n'))[0]
        self.assertEqual(row["Priority (Argument wise)"], 3)

    def test_reject_data_loss(self):
        for text in ('a,a\n1,2\n', 'a,\n1,2\n', 'a,b\n1,2,3\n', 'a,b\n1\n',
                     'a,b\n1,"unterminated'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                extract(io.StringIO(text))

    def test_explicit_delimiter_and_stream_ownership(self):
        stream = io.StringIO('x|payment_days\na|30\n')
        self.assertEqual(extract(stream, delimiter='|')[0]["Priority (Argument wise)"], 1)
        self.assertFalse(stream.closed)

    def test_known_bundled_sources_are_rejected_before_reading(self):
        for path in ("data/data/quotes.csv", "/tmp/kit/data/data/quotes.csv"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Bundled"):
                extract(path)
