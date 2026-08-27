import gzip
import tempfile
import unittest
from pathlib import Path

from logsieve import COMMON_LOG_FORMAT, TIMESTAMP_LEVEL_FORMAT, parse_stream
from logsieve.reader import open_log_lines


class OpenLogLinesTests(unittest.TestCase):
    def test_reads_plain_text_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.log"
            path.write_text("line one\nline two\nline three\n")
            lines = list(open_log_lines(path))
        self.assertEqual(lines, ["line one", "line two", "line three"])

    def test_reads_gzip_file_without_gz_extension(self):
        # rotated logs commonly end up named app.log.1, app.log.2, etc,
        # still gzip-compressed but without the .gz suffix
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.log.1"
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                fh.write("archived line\n")
            lines = list(open_log_lines(path))
        self.assertEqual(lines, ["archived line"])

    def test_result_is_lazily_iterated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.log"
            path.write_text("a\nb\n")
            result = open_log_lines(path)
            self.assertTrue(hasattr(result, "__next__"))


class ParseStreamTests(unittest.TestCase):
    def test_parses_common_log_format(self):
        lines = [
            '127.0.0.1 - - [28/Aug/2026:12:00:00 +0000] "GET /index.html HTTP/1.1" 200 512',
        ]
        records = list(parse_stream(lines, COMMON_LOG_FORMAT))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "200")
        self.assertEqual(records[0]["path"], "/index.html")

    def test_skips_unmatched_lines_by_default(self):
        lines = ["not a log line", "2026-08-28 12:00:00 INFO worker started"]
        records = list(parse_stream(lines, TIMESTAMP_LEVEL_FORMAT))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["level"], "INFO")

    def test_raises_on_unmatched_when_requested(self):
        lines = ["not a log line"]
        with self.assertRaises(ValueError):
            list(parse_stream(lines, TIMESTAMP_LEVEL_FORMAT, on_unmatched="raise"))


if __name__ == "__main__":
    unittest.main()
