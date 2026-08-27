"""Turn raw log lines into structured records using regex-based formats."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Optional


@dataclass(frozen=True)
class LogFormat:
    """A named regex with named capture groups.

    Field names come from the regex's group names rather than a separate
    list, so the pattern stays the single source of truth for what a
    parsed record looks like.
    """

    name: str
    pattern: re.Pattern

    @property
    def fields(self):
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


def parse_line(line: str, fmt: LogFormat) -> Optional[Dict[str, str]]:
    """Match a single line against a format, returning its fields or None."""
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
