# logsieve

A small library for reading and parsing log files without loading them
into memory.

## The problem

Log files are usually the one file on a box that doesn't fit the "just
read it into a string" pattern. A rotated nginx log or a week of app
output can easily run into gigabytes, and a lot of quick one-off scripts
(`open(path).readlines()`, `pandas.read_csv` on a log file, `.read().split("\n")`)
will happily try to hold the whole thing in RAM before doing anything
useful with it. That works fine on a laptop with a 10 MB test log and
falls over the first time it runs against production data.

logsieve is built around the opposite assumption: you should be able to
point it at a file of any size and get back an iterator, not a list.
Nothing in the core reading or parsing path buffers more than the current
line.

## Install

No dependencies, standard library only. For now:

```
pip install -e .
```

## Usage

Reading lines from a log file, gzip or not, without loading it into memory:

```python
from logsieve import open_log_lines

for line in open_log_lines("access.log.1"):  # transparently gzip-aware
    print(line)
```

Parsing lines against a known format as you stream them:

```python
from logsieve import open_log_lines, parse_stream, COMMON_LOG_FORMAT

lines = open_log_lines("access.log")
for record in parse_stream(lines, COMMON_LOG_FORMAT):
    if record["status"].startswith("5"):
        print(record["time"], record["path"], record["status"])
```

`parse_stream` never materializes the file - it pulls one line at a time
from whatever iterable you give it (a generator, an open file, a list)
and yields one parsed dict at a time. You can chain it straight off
`open_log_lines` and process a multi-gigabyte file with constant memory.

Built-in formats today:

- `COMMON_LOG_FORMAT` - the Apache/nginx combined access log format
- `TIMESTAMP_LEVEL_FORMAT` - generic `TIMESTAMP LEVEL message` lines, the
  kind most application loggers produce by default
- `SYSLOG_FORMAT` - RFC 3164 style syslog (`<34>Oct 11 22:14:15 host tag: message`);
  the `<priority>` prefix is optional since a lot of syslog forwarders strip it
- `JSON_LINES_FORMAT` - one JSON object per line, whatever keys it has

Define your own regex-based format with `compile_format`:

```python
from logsieve import compile_format, parse_line

fmt = compile_format("csv3", r"^(?P<a>[^,]+),(?P<b>[^,]+),(?P<c>.+)$")
parse_line("1,2,three", fmt)  # {'a': '1', 'b': '2', 'c': 'three'}
```

Not every format fits a single regex - `JSON_LINES_FORMAT` is built from a
plain `parse` function instead of a pattern. You can do the same for your
own formats: `LogFormat(name="mine", parse=my_parse_fn)`, where `my_parse_fn`
takes a line and returns a dict, or `None` to drop the line.

Filtering and counting parsed records without buffering the whole stream:

```python
from logsieve import open_log_lines, parse_stream, filter_records, count_by, field_equals, TIMESTAMP_LEVEL_FORMAT

records = parse_stream(open_log_lines("app.log"), TIMESTAMP_LEVEL_FORMAT)
errors = filter_records(records, field_equals("level", "ERROR"))
for record in errors:
    print(record["timestamp"], record["message"])
```

```python
records = parse_stream(open_log_lines("app.log"), TIMESTAMP_LEVEL_FORMAT)
count_by(records, "level")  # Counter({'INFO': 8123, 'WARN': 41, 'ERROR': 3})
```

`filter_records` stays lazy, like `parse_stream` - it only pulls the next
record when asked. `count_by` and `group_by` are terminal operations that
consume the whole stream, but `count_by` only ever holds the running
tallies in memory, not the records themselves, so it's still safe to run
over a huge file. `group_by` has to keep every record it sees (a bucket
isn't final until the stream ends), so it's meant for a filtered subset,
not the whole firehose. Predicate builders for the common cases -
`field_equals`, `field_in`, `field_matches` - save you from writing a
lambda for simple equality, membership, or regex checks; `count_by` and
`group_by` also take a field name directly instead of a key function for
the common "group by this one field" case.

## Status

The reading, parsing, filtering, and counting core works and is tested,
with a handful of built-in formats; rotation-aware multi-file reading,
follow mode, and CSV export are not built yet.

## License

MIT, see LICENSE.
