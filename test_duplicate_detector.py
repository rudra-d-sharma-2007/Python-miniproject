"""Tests for duplicate_detector: merge sort, duplicate scan, and CLI."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from duplicate_detector import (  # noqa: E402
    analyze,
    analyze_text,
    count_duplicates,
    find_duplicates,
    merge_sort,
    scan_duplicates,
    tokenize,
)

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "duplicate_detector.py")


class MergeSortTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(merge_sort([]), [])

    def test_single(self):
        self.assertEqual(merge_sort([7]), [7])

    def test_already_sorted(self):
        self.assertEqual(merge_sort([1, 2, 3, 4, 5]), [1, 2, 3, 4, 5])

    def test_reverse_sorted(self):
        self.assertEqual(merge_sort([5, 4, 3, 2, 1]), [1, 2, 3, 4, 5])

    def test_with_duplicates(self):
        self.assertEqual(merge_sort([3, 1, 3, 2, 1, 2]), [1, 1, 2, 2, 3, 3])

    def test_odd_and_even_lengths(self):
        self.assertEqual(merge_sort([9, -1, 4]), [-1, 4, 9])
        self.assertEqual(merge_sort([8, 2, 7, 1]), [1, 2, 7, 8])

    def test_matches_builtin_sorted(self):
        data = [42, -7, 3, 3, 100, 0, -7, 55, 12, 12, 12, 64, -20]
        self.assertEqual(merge_sort(data), sorted(data))

    def test_large_random(self):
        import random

        rng = random.Random(1234)
        data = [rng.randint(-1000, 1000) for _ in range(5000)]
        self.assertEqual(merge_sort(data), sorted(data))

    def test_does_not_mutate_input(self):
        data = [3, 1, 2]
        merge_sort(data)
        self.assertEqual(data, [3, 1, 2])

    def test_stable(self):
        # Pairs sorted by key must keep their original relative order.
        pairs = [("b", 1), ("a", 2), ("b", 3), ("a", 4), ("b", 5)]
        result = merge_sort(pairs)
        self.assertEqual([p for p in result if p[0] == "a"], [("a", 2), ("a", 4)])
        self.assertEqual([p for p in result if p[0] == "b"], [("b", 1), ("b", 3), ("b", 5)])

    def test_sorts_strings_and_floats(self):
        self.assertEqual(merge_sort(["pear", "apple", "apple"]), ["apple", "apple", "pear"])
        self.assertEqual(merge_sort([2.5, 1.1, 2.5]), [1.1, 2.5, 2.5])


class DuplicateScanTests(unittest.TestCase):
    def test_no_duplicates(self):
        self.assertEqual(find_duplicates([1, 2, 3, 4]), [])

    def test_empty_input(self):
        self.assertEqual(find_duplicates([]), [])

    def test_simple_duplicates(self):
        self.assertEqual(find_duplicates([3, 1, 2, 1, 3, 3]), [1, 3])

    def test_duplicates_at_boundaries(self):
        self.assertEqual(find_duplicates([5, 5, 1, 2, 9, 9]), [5, 9])

    def test_triple_and_quadruple(self):
        self.assertEqual(find_duplicates([7, 7, 7, 7, 1, 1]), [1, 7])

    def test_output_is_sorted_and_unique(self):
        result = find_duplicates([9, 9, 2, 2, 5, 5, 2, 9])
        self.assertEqual(result, [2, 5, 9])

    def test_counts(self):
        self.assertEqual(count_duplicates([1, 2, 1, 3, 1, 2]), [(1, 3), (2, 2)])

    def test_strings(self):
        self.assertEqual(find_duplicates(["x", "y", "x", "z"]), ["x"])

    def test_large_input(self):
        # 1..1000 each appearing once, then 1..100 repeated twice more.
        data = list(range(1, 1001)) + [n for n in range(1, 101) for _ in range(2)]
        result = find_duplicates(data)
        self.assertEqual(result, list(range(1, 101)))


class ScanAndAnalyzeTests(unittest.TestCase):
    def test_scan_duplicates_on_pre_sorted(self):
        self.assertEqual(scan_duplicates([1, 1, 2, 3, 3, 3]), [(1, 2), (3, 3)])

    def test_scan_duplicates_clean(self):
        self.assertEqual(scan_duplicates([1, 2, 3]), [])

    def test_analyze_basic(self):
        report = analyze([3, 1, 3, 2, 1, 3])
        self.assertEqual(report["total_items"], 6)
        self.assertEqual(report["unique_count"], 3)
        self.assertEqual(report["duplicate_count"], 2)
        self.assertEqual(report["duplicate_items"], 3)
        self.assertEqual(report["sorted"], [1, 1, 2, 3, 3, 3])
        self.assertEqual(
            report["duplicates"],
            [{"value": 1, "occurrences": 2}, {"value": 3, "occurrences": 3}],
        )
        self.assertGreaterEqual(report["sort_ms"], 0.0)
        self.assertGreaterEqual(report["scan_ms"], 0.0)

    def test_analyze_no_duplicates(self):
        report = analyze([1, 2, 3])
        self.assertEqual(report["duplicate_count"], 0)
        self.assertEqual(report["unique_count"], 3)
        self.assertEqual(report["duplicates"], [])

    def test_analyze_empty(self):
        report = analyze([])
        self.assertEqual(report["total_items"], 0)
        self.assertEqual(report["sorted"], [])
        self.assertEqual(report["duplicates"], [])

    def test_analyze_is_json_serializable(self):
        import json

        payload = json.dumps(analyze([2.5, 1.5, 2.5]))
        self.assertIn('"duplicate_count": 1', payload)

    def test_analyze_text_parses_tokens(self):
        report = analyze_text("b a, c b\n a")
        self.assertEqual(report["total_items"], 5)
        self.assertEqual([d["value"] for d in report["duplicates"]], ["a", "b"])

    def test_analyze_text_numbers(self):
        report = analyze_text("10 20 10", as_number=True)
        self.assertEqual(report["duplicates"], [{"value": 10, "occurrences": 2}])

    def test_analyze_text_rejects_bad_number(self):
        with self.assertRaises(ValueError):
            analyze_text("1 abc", as_number=True)


class TokenizeTests(unittest.TestCase):
    def test_whitespace_and_commas(self):
        self.assertEqual(tokenize("a b,c\nd"), ["a", "b", "c", "d"])

    def test_empty(self):
        self.assertEqual(tokenize("   \n"), [])


class CliTests(unittest.TestCase):
    def run_cli(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, SCRIPT, *args],
            input=stdin,
            capture_output=True,
            text=True,
        )

    def test_items_flag(self):
        proc = self.run_cli("--items", "4", "2", "7", "2", "4", "4")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Found 2 duplicates among 6 items", proc.stdout)
        self.assertIn("2", proc.stdout)
        self.assertIn("4", proc.stdout)

    def test_stdin_no_duplicates(self):
        proc = self.run_cli(stdin="1 2 3 4 5\n")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("No duplicates found among 5 items", proc.stdout)

    def test_numbers_with_counts(self):
        proc = self.run_cli("--numbers", "--counts", stdin="10 20 10 30 10\n")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("10 (x3)", proc.stdout)

    def test_json_output(self):
        proc = self.run_cli("--numbers", "--counts", "--json", stdin="1 2 1 2 2\n")
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["total_items"], 5)
        self.assertEqual(payload["duplicate_count"], 2)
        self.assertEqual(
            payload["duplicates"],
            [{"value": 1, "occurrences": 2}, {"value": 2, "occurrences": 3}],
        )

    def test_file_input(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_input.txt")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("dog cat dog bird\n")
            proc = self.run_cli(path)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("dog", proc.stdout)
        finally:
            os.remove(path)

    def test_quiet_exit_code(self):
        self.assertEqual(self.run_cli("--quiet", stdin="1 2 3").returncode, 0)
        self.assertEqual(self.run_cli("--quiet", stdin="1 2 1").returncode, 1)

    def test_numbers_rejects_non_numeric(self):
        proc = self.run_cli("--numbers", "--items", "1", "abc")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not numeric", proc.stderr)

    def test_file_and_items_conflict(self):
        proc = self.run_cli("somefile.txt", "--items", "1", "1")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
