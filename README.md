# Python-miniproject — dupescan

A duplicate detection tool that **sorts the data first with merge sort**, then finds duplicates with a single linear scan. One Python module, three surfaces: a **browser app**, a **CLI**, and a **library**.

## Browser app

The web UI runs the *same* `duplicate_detector.py` unmodified inside your browser via [Pyodide](https://pyodide.org) (CPython compiled to WebAssembly) — your data never leaves your tab.

- Paste or load any list, toggle numeric parsing and occurrence counts, and get a full report: duplicated values, extra copies, the sorted output, and a phase bar showing time spent in merge sort vs. the adjacent scan.
- Runtime loads from the jsdelivr CDN on first visit; everything after that is local.
- Architecture: `web/` holds the static site, which fetches `duplicate_detector.py` at startup, writes it into Pyodide's in-memory filesystem, imports it, and calls `analyze_text()` through a JSON bridge. No server-side code, fully static hosting.

```bash
# Preview (stages web/ + the module into .preview-site/ and serves it)
sh ./scripts/serve.sh            # PORT=xxxx to override the default 8000

# Production build: static output in dist/
sh ./scripts/build.sh
```

## How it works

1. **Merge sort** (O(n log n), stable) puts equal values next to each other.
2. **Linear scan** (O(n)) compares adjacent elements once — no hash table, no nested loops.

Total: O(n log n) time, O(n) space, with the sorted order available for free.

## CLI

```bash
# Inline items
python3 duplicate_detector.py --items banana apple banana cherry apple banana

# From a file
python3 duplicate_detector.py data.txt

# From stdin
printf '10 20 30 20 40 30 30\n' | python3 duplicate_detector.py --numbers --counts

# Machine-readable output
printf '1 2 1\n' | python3 duplicate_detector.py --numbers --json

# Script-friendly: silent, exit code 0 = clean, 1 = duplicates found
python3 duplicate_detector.py --quiet data.txt
```

| Flag | Description |
| --- | --- |
| `path` | Input file (default: read from stdin) |
| `-i, --items ...` | Inline values instead of a file |
| `-n, --numbers` | Parse tokens as int/float instead of strings |
| `-c, --counts` | Show occurrence counts for each duplicate |
| `--json` | Emit results as JSON |
| `-q, --quiet` | Print nothing; rely on the exit code (0 = clean, 1 = duplicates) |

Input is split on whitespace and commas, so `"a b,c"` and newline-separated file rows both work.

## Library API

```python
from duplicate_detector import (
    merge_sort, scan_duplicates, find_duplicates, count_duplicates,
    analyze, analyze_text,
)

merge_sort([3, 1, 2])              # [1, 2, 3]  — stable top-down merge sort
scan_duplicates([1, 1, 2, 3, 3])   # [(1, 2), (3, 2)] — the O(n) pass
find_duplicates([3, 1, 3, 1])      # [1, 3]
count_duplicates([3, 1, 3, 1])     # [(1, 2), (3, 2)]
analyze([3, 1, 3])                 # JSON-serializable report with sort/scan timings
analyze_text("3 1 3", as_number=True)  # same, from raw text (used by the web UI)
```

## Tests

```bash
python3 -m unittest test_duplicate_detector -v
```

39 tests cover the sort (correctness, stability, edge cases vs. `sorted()`), the scan, the analysis report, and the CLI end to end.
