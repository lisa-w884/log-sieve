"""Streaming line reader for log files, including gzip-compressed ones."""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import Iterator, Union

PathLike = Union[str, Path]


def _looks_gzipped(path: Path) -> bool:
    if path.suffix == ".gz":
        return True
    # Rotated logs often lose the .gz suffix (app.log.1, app.log.2, ...)
    # once a rotator has compressed and renumbered them, so fall back to
    # sniffing the gzip magic bytes.
    try:
        with open(path, "rb") as fh:
            magic = fh.read(2)
    except OSError:
        return False
    return magic == b"\x1f\x8b"


def open_log_lines(
    path: PathLike,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> Iterator[str]:
    """Yield lines from a log file one at a time.

    Handles gzip-compressed files transparently. Lines come back with the
    trailing newline stripped. This is a generator backed directly by the
    underlying file handle - nothing here reads the file into memory up
    front, so iterating a 10 GB log costs the same memory as a 10 KB one.
    The handle is closed once the generator is exhausted or closed.
    """
    p = Path(path)
    opener = gzip.open if _looks_gzipped(p) else open
    fh = opener(p, mode="rt", encoding=encoding, errors=errors, newline="")
    try:
        for raw_line in fh:
            yield raw_line.rstrip("\n").rstrip("\r")
    finally:
        fh.close()
