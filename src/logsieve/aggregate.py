"""Filtering and counting helpers for streams of parsed records."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, Iterable, Iterator, List, Union

Record = Dict[str, Any]
Predicate = Callable[[Record], bool]
KeyFunc = Union[str, Callable[[Record], Any]]


def _as_key_func(key: KeyFunc) -> Callable[[Record], Any]:
    # a bare field name is the common case, so let callers pass "status"
    # instead of always writing out a lambda
    if callable(key):
        return key
    field = key
    return lambda record: record.get(field)


def field_equals(field: str, value: Any) -> Predicate:
    """Predicate: record[field] == value."""
    return lambda record: record.get(field) == value


def field_in(field: str, values: Iterable[Any]) -> Predicate:
    """Predicate: record[field] is one of `values`."""
    allowed = set(values)
    return lambda record: record.get(field) in allowed


def field_matches(field: str, pattern: str) -> Predicate:
    """Predicate: record[field] (as a string) matches `pattern` anywhere."""
    compiled = re.compile(pattern)
    return lambda record: compiled.search(str(record.get(field, ""))) is not None


def filter_records(records: Iterable[Record], predicate: Predicate) -> Iterator[Record]:
    """Yield only the records for which `predicate(record)` is truthy.

    Pulls from `records` lazily, so this composes with `parse_stream` the
    same way it composes with `open_log_lines` - nothing here buffers more
    than the current record.
    """
    for record in records:
        if predicate(record):
            yield record


def count_by(records: Iterable[Record], key: KeyFunc) -> Counter:
    """Count records per key, consuming `records` in a single streaming pass.

    `key` is either a field name or a callable taking a record and
    returning the value to group on. Only the tallies are kept in memory,
    not the records themselves, so this is safe to run over a stream
    backed by a multi-gigabyte file.
    """
    key_func = _as_key_func(key)
    counts: Counter = Counter()
    for record in records:
        counts[key_func(record)] += 1
    return counts


def group_by(records: Iterable[Record], key: KeyFunc) -> Dict[Any, List[Record]]:
    """Bucket records by key, preserving each bucket's original order.

    Unlike `filter_records` and `count_by`, this has to hold every record
    it sees since a record's final bucket isn't known until the whole
    stream has been read. Fine for a day's worth of matching lines; not
    the right tool for grouping an entire firehose log by something with
    unbounded cardinality.
    """
    key_func = _as_key_func(key)
    groups: Dict[Any, List[Record]] = defaultdict(list)
    for record in records:
        groups[key_func(record)].append(record)
    return dict(groups)
