"""Parse a GALDR voice loop log file and report latency statistics.

Usage:
    python parse_benchmark.py benchmark_01.log
    python parse_benchmark.py benchmark_01.log benchmark_02.log ...
    cat benchmark_01.log | python parse_benchmark.py -
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Patterns — each maps a label to a regex capturing one float value
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("TTFA (input -> first audio)",     re.compile(r"\[STREAM TTFA\] (\d+(?:\.\d+)?)ms to first sentence")),
    ("Pre-LLM overhead (steps 1-4)",   re.compile(r"\[STREAM\] steps 1-4 done in (\d+(?:\.\d+)?)ms")),
    ("LLM first token",                re.compile(r"\[LLM STREAM\] first_token_ms=(\d+(?:\.\d+)?)")),
    ("LLM total stream",               re.compile(r"\[LLM STREAM\] total_ms=(\d+(?:\.\d+)?)")),
    ("ElevenLabs TTS synthesis",       re.compile(r"\[EL TTS\] chars=\d+ bytes=\d+ latency_ms=(\d+(?:\.\d+)?)")),
    ("Azure TTS synthesis",            re.compile(r"\[TTS\] voice=\S+ chars=\d+ latency_ms=(\d+(?:\.\d+)?)")),
    ("LLM call (non-streaming)",       re.compile(r"\[LLM CALL\] tokens_in=\d+ tokens_out=\d+ latency_ms=(\d+(?:\.\d+)?)")),
]


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = (p / 100) * (len(s) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return s[lo] + (idx - lo) * (s[hi] - s[lo])


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    return {
        "n":    len(values),
        "min":  min(values),
        "mean": sum(values) / len(values),
        "p50":  _percentile(values, 50),
        "p95":  _percentile(values, 95),
        "max":  max(values),
    }


def parse_lines(lines: list[str]) -> dict[str, list[float]]:
    results: dict[str, list[float]] = {label: [] for label, _ in _PATTERNS}
    for line in lines:
        for label, pat in _PATTERNS:
            m = pat.search(line)
            if m:
                results[label].append(float(m.group(1)))
    return results


def report(results: dict[str, list[float]]) -> None:
    print(f"\n{'Metric':<35} {'n':>4}  {'min':>7}  {'mean':>7}  {'p50':>7}  {'p95':>7}  {'max':>7}")
    print("-" * 80)
    for label, values in results.items():
        if not values:
            continue
        s = _stats(values)
        print(
            f"{label:<35} {s['n']:>4.0f}  "
            f"{s['min']:>6.0f}ms  {s['mean']:>6.0f}ms  "
            f"{s['p50']:>6.0f}ms  {s['p95']:>6.0f}ms  {s['max']:>6.0f}ms"
        )
    print()

    ttfa = results.get("TTFA (input -> first audio)", [])
    if ttfa:
        s = _stats(ttfa)
        target = 500
        pct_under = sum(1 for v in ttfa if v < target) / len(ttfa) * 100
        print(f"Target p95 < {target}ms: {'PASS' if s['p95'] < target else 'MISS'}  "
              f"({pct_under:.0f}% of turns under {target}ms)")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse GALDR benchmark log for latency stats")
    parser.add_argument("files", nargs="*", default=["-"], help="Log files to parse (- for stdin)")
    args = parser.parse_args()

    all_lines: list[str] = []
    for path in args.files:
        if path == "-":
            all_lines.extend(sys.stdin.readlines())
        else:
            p = Path(path)
            if not p.exists():
                print(f"File not found: {path}", file=sys.stderr)
                continue
            all_lines.extend(p.read_text(encoding="utf-8", errors="replace").splitlines())

    if not all_lines:
        print("No input.", file=sys.stderr)
        sys.exit(1)

    results = parse_lines(all_lines)
    total = sum(len(v) for v in results.values())
    if total == 0:
        print("No benchmark entries found. Is this the right log file?", file=sys.stderr)
        sys.exit(1)

    report(results)


if __name__ == "__main__":
    main()
