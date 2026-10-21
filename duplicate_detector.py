#!/usr/bin/env python3
"""Duplicate detection tool.

Strategy: sort the data first with merge sort (O(n log n)), then make a
single linear pass (O(n)) comparing adjacent elements to find duplicates.
Sorting once up front turns duplicate detection into a cheap scan with no
hash table and full ordering preserved.

The same module powers three surfaces: this CLI, the unit tests, and the
browser UI (web/), where it runs unmodified inside Pyodide (CPython compiled
to WebAssembly) so data never leaves the user's tab.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Iterable, List, Sequence, Tuple, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Merge sort
# ---------------------------------------------------------------------------

def merge_sort(items: Iterable[T]) -> List[T]:
    """Return a new sorted list using top-down merge sort.

    Stable, O(n log n) time, O(n) auxiliary space.
    """
    items = list(items)
    if len(items) <= 1:
        return items
    mid = len(items) // 2
    return _merge(merge_sort(items[:mid]), merge_sort(items[mid:]))


def _merge(left: List[T], right: List[T]) -> List[T]:
    """Merge two sorted lists into one sorted list (stable)."""
    merged: List[T] = []
    i = j = 0
    left_len, right_len = len(left), len(right)
    # Append whichever side's head is smaller; ties take from the left half
    # so equal elements keep their original relative order (stability).
    while i < left_len and j < right_len:
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    if i < left_len:
        merged.extend(left[i:])
    if j < right_len:
        merged.extend(right[j:])
    return merged


# ---------------------------------------------------------------------------
# Duplicate scan
# ---------------------------------------------------------------------------

def scan_duplicates(sorted_items: Sequence[T]) -> List[Tuple[T, int]]:
    """Single linear pass (O(n)) over already-sorted items.

    Returns (value, occurrences) for every value that appears more than
    once, in sorted order. This is the scan half of the tool; callers that
    have not sorted yet should use count_duplicates().
    """
    results: List[Tuple[T, int]] = []
    i = 0
    n = len(sorted_items)
    while i < n:
        j = i
        # All equal values are now adjacent thanks to the sort, so one
        # forward scan finds every duplicate group.
        while j + 1 < n and sorted_items[j + 1] == sorted_items[i]:
            j += 1
        if j > i:
            results.append((sorted_items[i], j - i + 1))
        i = j + 1
    return results


def find_duplicates(items: Iterable[T]) -> List[T]:
    """Sort with merge sort, then scan adjacent pairs for duplicates.

    Returns the duplicated values in sorted order, each listed once.
    """
    return [value for value, _ in count_duplicates(items)]


def count_duplicates(items: Iterable[T]) -> List[Tuple[T, int]]:
    """Sort with merge sort, then return (value, occurrences) for values
    that appear more than once, in sorted order.
    """
    return scan_duplicates(merge_sort(items))


# ---------------------------------------------------------------------------
# Analysis report (shared by the browser UI and anything wanting metrics)
# ---------------------------------------------------------------------------

def analyze(values: Iterable[T]) -> dict:
    """Sort, scan, and return a JSON-serializable report with timings.

    Timing splits the two phases so the UI can show exactly what the
    sort-then-scan strategy costs.
    """
    values = list(values)
    t0 = time.perf_counter()
    ordered = merge_sort(values)
    t1 = time.perf_counter()
    duplicates = scan_duplicates(ordered)
    t2 = time.perf_counter()

    extra_copies = sum(count - 1 for _, count in duplicates)
    return {
        "total_items": len(values),
        "unique_count": len(values) - extra_copies,
        "duplicate_count": len(duplicates),
        "duplicate_items": extra_copies,
        "sort_ms": round((t1 - t0) * 1000.0, 3),
        "scan_ms": round((t2 - t1) * 1000.0, 3),
        "duplicates": [{"value": v, "occurrences": c} for v, c in duplicates],
        "sorted": ordered,
    }


def analyze_text(text: str, as_number: bool = False) -> dict:
    """Tokenize raw text and run analyze() on it. Used by the browser UI."""
    values = [parse_value(tok, as_number) for tok in tokenize(text)]
    return analyze(values)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def die(message: str) -> None:
    """Print a usage-style error and exit with status 2 (like argparse)."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_value(token: str, as_number: bool):
    if not as_number:
        return token
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            raise ValueError(f"--numbers given but {token!r} is not numeric") from None


def tokenize(text: str) -> List[str]:
    """Split input on whitespace and commas so 'a,b c' and file lines both work."""
    cleaned = text.replace(",", " ")
    return cleaned.split()


def read_source(path: str | None, items_arg: list[str] | None) -> str:
    if items_arg is not None:
        return " ".join(items_arg)
    if path is not None:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            die(f"cannot read {path}: {exc.strerror}")
    if sys.stdin.isatty():
        die("no input. Pass a file, pipe data via stdin, or use --items")
    return sys.stdin.read()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duplicate_detector",
        description=(
            "Detect duplicates by first sorting the data with merge sort, "
            "then scanning adjacent elements in a single linear pass."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="input file (default: read from stdin)",
    )
    parser.add_argument(
        "-i",
        "--items",
        nargs="+",
        metavar="ITEM",
        help="inline values instead of a file, e.g. --items 4 2 7 2",
    )
    parser.add_argument(
        "-n",
        "--numbers",
        action="store_true",
        help="treat input tokens as numbers (int/float) instead of strings",
    )
    parser.add_argument(
        "-c",
        "--counts",
        action="store_true",
        help="show how many times each duplicated value occurs",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit results as JSON",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="print nothing; use the exit code (0 = clean, 1 = duplicates found)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.path is not None and args.items is not None:
        die("pass either a file or --items, not both")

    text = read_source(args.path, args.items)
    tokens = tokenize(text)
    try:
        values = [parse_value(tok, args.numbers) for tok in tokens]
    except ValueError as exc:
        die(str(exc))

    duplicates = count_duplicates(values)

    if args.quiet:
        return 1 if duplicates else 0

    if args.as_json:
        payload = {
            "total_items": len(values),
            "duplicate_count": len(duplicates),
            "duplicates": (
                [{"value": v, "occurrences": c} for v, c in duplicates]
                if args.counts
                else [v for v, _ in duplicates]
            ),
        }
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not duplicates:
            print(f"No duplicates found among {len(values)} items.")
        else:
            noun = "duplicate" if len(duplicates) == 1 else "duplicates"
            print(f"Found {len(duplicates)} {noun} among {len(values)} items:")
            for value, count in duplicates:
                if args.counts:
                    print(f"  {value} (x{count})")
                else:
                    print(f"  {value}")
    return 1 if duplicates else 0


if __name__ == "__main__":
    raise SystemExit(main())
