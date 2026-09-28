#!/usr/bin/env python3
"""Aggregate tools/agents/delegate.py's usage.jsonl into a per-role report.

Reads one JSON object per line (see delegate.py's log_usage /
build_usage_record) and prints, per agent, call counts by verdict, summed
token/cost figures, and median duration. Malformed lines are skipped and
counted rather than aborting the report.
"""

from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[2]
_DEFAULT_LOG = _REPO_ROOT / ".harness" / "usage.jsonl"

STATUSES = ("PASS", "FAIL", "BLOCKED")

_SUM_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "cost_usd",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        help="Only include records at/after this UTC date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print a machine-readable JSON report"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=_DEFAULT_LOG,
        help="Usage log path (default: %(default)s)",
    )
    return parser


def parse_since(raw: str) -> datetime.datetime:
    try:
        return datetime.datetime.strptime(raw, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError as exc:
        raise SystemExit(f"invalid --since date (want YYYY-MM-DD): {raw}") from exc


def _record_timestamp(record: dict[str, Any]) -> datetime.datetime | None:
    ts = record.get("ts")
    if not isinstance(ts, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def load_records(
    path: Path, *, since: datetime.datetime | None
) -> tuple[list[dict[str, Any]], int]:
    """Read usage.jsonl, tolerating malformed lines.

    Returns (records, malformed_line_count). A missing file is treated as
    an empty log, not an error.
    """
    records: list[dict[str, Any]] = []
    malformed = 0
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return records, malformed
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(record, dict) or not isinstance(record.get("agent"), str):
            malformed += 1
            continue
        if since is not None:
            ts = _record_timestamp(record)
            if ts is None:
                malformed += 1
                continue
            if ts < since:
                continue
        records.append(record)
    return records, malformed


def _sum_optional(values: list[Any]) -> float | int | None:
    numeric = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not numeric:
        return None
    total = sum(numeric)
    if all(isinstance(v, int) for v in numeric):
        return total
    return float(total)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {status: 0 for status in STATUSES}
    other_status = 0
    for row in rows:
        status = row.get("status")
        if status in counts:
            counts[status] += 1
        else:
            other_status += 1
    durations = [
        row["duration_s"]
        for row in rows
        if isinstance(row.get("duration_s"), (int, float))
        and not isinstance(row.get("duration_s"), bool)
    ]
    summary: dict[str, Any] = {
        "calls": len(rows),
        "pass": counts["PASS"],
        "fail": counts["FAIL"],
        "blocked": counts["BLOCKED"],
        "other_status": other_status,
        "median_duration_s": statistics.median(durations) if durations else None,
    }
    for field in _SUM_FIELDS:
        summary[field] = _sum_optional([row.get(field) for row in rows])
    return summary


def aggregate(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_agent.setdefault(record["agent"], []).append(record)

    report: dict[str, dict[str, Any]] = {}
    for agent in sorted(by_agent):
        report[agent] = _summarize(by_agent[agent])
    if records:
        report["TOTAL"] = _summarize(records)
    return report


def _fmt(value: Any, *, money: bool = False, decimals: int = 0) -> str:
    if value is None:
        return "-"
    if money:
        return f"{value:.4f}"
    if decimals:
        return f"{value:.{decimals}f}"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def render_table(report: dict[str, dict[str, Any]]) -> str:
    headers = [
        "agent", "calls", "pass", "fail", "blocked",
        "in_tok", "out_tok", "cache_r", "cache_c", "cost_usd", "median_s",
    ]
    rows = []
    for agent, s in report.items():
        rows.append(
            [
                agent,
                str(s["calls"]),
                str(s["pass"]),
                str(s["fail"]),
                str(s["blocked"]),
                _fmt(s["input_tokens"]),
                _fmt(s["output_tokens"]),
                _fmt(s["cache_read_tokens"]),
                _fmt(s["cache_creation_tokens"]),
                _fmt(s["cost_usd"], money=True),
                _fmt(s["median_duration_s"], decimals=2),
            ]
        )
    widths = [
        max([len(headers[i])] + [len(row[i]) for row in rows])
        for i in range(len(headers))
    ]
    lines = [
        "  ".join(h.ljust(w) for h, w in zip(headers, widths)),
        "  ".join("-" * w for w in widths),
    ]
    for row in rows:
        lines.append("  ".join(c.ljust(w) for c, w in zip(row, widths)))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    since = parse_since(args.since) if args.since else None
    records, malformed = load_records(args.file, since=since)
    report = aggregate(records)

    if args.json:
        print(
            json.dumps(
                {"file": str(args.file), "malformed_lines": malformed, "agents": report},
                indent=2,
                sort_keys=True,
            )
        )
    else:
        if not report:
            print(f"no usage records found in {args.file}")
        else:
            print(render_table(report))
        if malformed:
            print(f"\n{malformed} malformed line(s) skipped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
