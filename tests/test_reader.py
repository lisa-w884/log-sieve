import gzip
import tempfile
import unittest
from pathlib import Path

from logsieve import (
    COMMON_LOG_FORMAT,
    JSON_LINES_FORMAT,
    SYSLOG_FORMAT,
    TIMESTAMP_LEVEL_FORMAT,
    parse_stream,
)
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

    def test_parses_syslog_format(self):
        lines = ["<34>Oct 11 22:14:15 mymachine su[1234]: 'su root' failed for lonvick"]
        records = list(parse_stream(lines, SYSLOG_FORMAT))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["priority"], "34")
        self.assertEqual(records[0]["host"], "mymachine")
        self.assertEqual(records[0]["tag"], "su[1234]")
        self.assertEqual(records[0]["message"], "'su root' failed for lonvick")

    def test_parses_syslog_format_without_priority(self):
        lines = ["Oct 11 22:14:15 mymachine cron: job started"]
        records = list(parse_stream(lines, SYSLOG_FORMAT))
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["priority"])
        self.assertEqual(records[0]["tag"], "cron")

    def test_parses_json_lines_format(self):
        lines = [
            '{"level": "info", "msg": "worker started", "pid": 42}',
            '{"level": "error", "msg": "connection lost"}',
        ]
        records = list(parse_stream(lines, JSON_LINES_FORMAT))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["pid"], 42)
        self.assertEqual(records[1]["level"], "error")

    def test_skips_malformed_and_non_object_json_lines(self):
        lines = ["not json", "[1, 2, 3]", "", '{"ok": true}']
        records = list(parse_stream(lines, JSON_LINES_FORMAT))
        self.assertEqual(records, [{"ok": True}])


if __name__ == "__main__":
    unittest.main()
