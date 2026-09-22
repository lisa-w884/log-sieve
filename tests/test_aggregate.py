import unittest

from logsieve import (
    count_by,
    field_equals,
    field_in,
    field_matches,
    filter_records,
    group_by,
)


def records():
    return [
        {"level": "INFO", "message": "worker started"},
        {"level": "ERROR", "message": "connection lost"},
        {"level": "INFO", "message": "worker finished"},
        {"level": "WARN", "message": "queue backing up"},
    ]


class FieldPredicateTests(unittest.TestCase):
    def test_field_equals(self):
        result = list(filter_records(records(), field_equals("level", "ERROR")))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["message"], "connection lost")

    def test_field_in(self):
        pred = field_in("level", ["INFO", "WARN"])
        result = list(filter_records(records(), pred))
        self.assertEqual([r["level"] for r in result], ["INFO", "INFO", "WARN"])

    def test_field_matches(self):
        pred = field_matches("message", r"^worker")
        result = list(filter_records(records(), pred))
        self.assertEqual(len(result), 2)

    def test_field_matches_missing_field_does_not_raise(self):
        pred = field_matches("nope", r"anything")
        result = list(filter_records(records(), pred))
        self.assertEqual(result, [])


class FilterRecordsTests(unittest.TestCase):
    def test_is_lazy(self):
        result = filter_records(records(), field_equals("level", "INFO"))
        self.assertTrue(hasattr(result, "__next__"))

    def test_custom_callable_predicate(self):
        result = list(filter_records(records(), lambda r: len(r["message"]) > 15))
        self.assertEqual(len(result), 3)


class CountByTests(unittest.TestCase):
    def test_counts_by_field_name(self):
        counts = count_by(records(), "level")
        self.assertEqual(counts["INFO"], 2)
        self.assertEqual(counts["ERROR"], 1)
        self.assertEqual(counts["WARN"], 1)

    def test_counts_by_callable_key(self):
        counts = count_by(records(), lambda r: r["message"].split()[0])
        self.assertEqual(counts["worker"], 2)
        self.assertEqual(counts["connection"], 1)

    def test_empty_stream_gives_empty_counter(self):
        counts = count_by([], "level")
        self.assertEqual(counts, {})


class GroupByTests(unittest.TestCase):
    def test_groups_preserve_order_within_bucket(self):
        groups = group_by(records(), "level")
        self.assertEqual(
            [r["message"] for r in groups["INFO"]],
            ["worker started", "worker finished"],
        )
        self.assertEqual(len(groups["ERROR"]), 1)
        self.assertEqual(set(groups.keys()), {"INFO", "ERROR", "WARN"})

    def test_unknown_key_field_groups_under_none(self):
        groups = group_by(records(), "nope")
        self.assertEqual(len(groups[None]), 4)


if __name__ == "__main__":
    unittest.main()
