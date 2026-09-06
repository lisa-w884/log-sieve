"""Turn raw log lines into structured records using named formats."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Iterator, Optional


@dataclass(frozen=True)
class LogFormat:
    """A named way to turn one line of text into a dict, or reject it.

    Most formats are a regex with named capture groups, in which case
    field names come from the regex's group names rather than a separate
    list, so the pattern stays the single source of truth for what a
    parsed record looks like. Formats that aren't line-oriented regexes
    (JSON lines, say) can instead supply a `parse` callable that takes a
    line and returns a dict or None.
    """

    name: str
    pattern: Optional[re.Pattern] = None
    parse: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None

    def __post_init__(self):
        if self.pattern is None and self.parse is None:
            raise ValueError("LogFormat needs either a pattern or a parse function")

    @property
    def fields(self):
        if self.pattern is None:
            return ()
        return tuple(self.pattern.groupindex.keys())


def compile_format(name: str, pattern: str) -> LogFormat:
    return LogFormat(name=name, pattern=re.compile(pattern))


# Apache/nginx "combined" style common log format, e.g.:
# 127.0.0.1 - - [28/Aug/2026:12:00:00 +0000] "GET /index.html HTTP/1.1" 200 512
COMMON_LOG_FORMAT = compile_format(
    "common",
    r"^(?P<host>\S+) \S+ (?P<user>\S+) \[(?P<time>[^\]]+)\] "
    r'"(?P<method>\S+) (?P<path>\S+) (?P<protocol>[^"]+)" '
    r"(?P<status>\d{3}) (?P<size>\d+|-)$",
)

# A generic "timestamp LEVEL message" line, e.g.:
# 2026-08-28 12:00:00 INFO worker started
TIMESTAMP_LEVEL_FORMAT = compile_format(
    "timestamp_level",
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?) "
    r"(?P<level>[A-Z]+) (?P<message>.*)$",
)

# RFC 3164 style syslog, e.g.:
# <34>Oct 11 22:14:15 mymachine su[1234]: 'su root' failed for lonvick
# The <34> priority prefix is optional since plenty of syslog consumers
# (journald forwarders, docker log drivers) strip it before writing to disk.
SYSLOG_FORMAT = compile_format(
    "syslog",
    r"^(?:<(?P<priority>\d{1,3})>)?"
    r"(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s\d{2}:\d{2}:\d{2})\s"
    r"(?P<host>\S+)\s"
    r"(?P<tag>[^:\s]+):\s(?P<message>.*)$",
)


def _parse_json_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


# JSON-lines logs, one JSON object per line, e.g. what most structured
# loggers (structlog, pino, zap in JSON mode) emit by default. There's no
# regex here since the field set is whatever keys the object happens to
# have - `fields` on this format is always empty, unlike the regex ones.
JSON_LINES_FORMAT = LogFormat(name="json_lines", parse=_parse_json_line)


def parse_line(line: str, fmt: LogFormat) -> Optional[Dict[str, Any]]:
    """Match a single line against a format, returning its fields or None."""
    if fmt.parse is not None:
        return fmt.parse(line)
    match = fmt.pattern.match(line)
    if match is None:
        return None
    return match.groupdict()


def parse_stream(
    lines: Iterable[str],
    fmt: LogFormat,
    on_unmatched: str = "skip",
) -> Iterator[Dict[str, str]]:
    """Parse an iterable of lines, yielding one dict per matching line.

    `lines` is consumed lazily, one item at a time, so this composes with
    `reader.open_log_lines` to process arbitrarily large files without ever
    holding the whole thing in memory. `on_unmatched` controls what happens
    when a line doesn't match: "skip" drops it, "raise" raises ValueError
    with the offending line included.
    """
    if on_unmatched not in ("skip", "raise"):
        raise ValueError(f"on_unmatched must be 'skip' or 'raise', got {on_unmatched!r}")

    for line in lines:
        record = parse_line(line, fmt)
        if record is None:
            if on_unmatched == "raise":
                raise ValueError(f"line did not match format {fmt.name!r}: {line!r}")
            continue
        yield record
