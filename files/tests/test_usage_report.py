"""Tests for tools/agents/usage_report.py: per-agent aggregation of the
usage.jsonl log written by delegate.py's log_usage (see test_usage_log.py).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "tools" / "agents" / "usage_report.py"
_SPEC = importlib.util.spec_from_file_location("usage_report", _SCRIPT)
assert _SPEC and _SPEC.loader
usage_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(usage_report)


def _record(**overrides: Any) -> dict[str, Any]:
    base = {
        "ts": "2026-01-01T00:00:00+00:00",
        "agent": "codebase-explorer",
        "provider": "Claude Code CLI",
        "model": "claude-sonnet-5",
        "status": "PASS",
        "smoke": False,
        "duration_s": 1.0,
        "exit_code": 0,
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_tokens": 1,
        "cache_creation_tokens": 2,
        "cost_usd": 0.01,
        "task_sha256": "deadbeef",
        "task_chars": 20,
    }
    base.update(overrides)
    return base


def write_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def test_missing_file_yields_empty_report(tmp_path: Path) -> None:
    records, malformed = usage_report.load_records(tmp_path / "absent.jsonl", since=None)
    assert records == []
    assert malformed == 0
    assert usage_report.aggregate(records) == {}


def test_malformed_lines_are_skipped_and_counted(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    write_log(
        log,
        [
            json.dumps(_record()),
            "not json at all",
            "{'single': 'quotes not valid json'}",
            json.dumps(["not", "an", "object"]),
            json.dumps({"no_agent_field": True}),
        ],
    )

    records, malformed = usage_report.load_records(log, since=None)

    assert len(records) == 1
    assert malformed == 4


def test_aggregate_sums_tokens_cost_and_counts_status(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    write_log(
        log,
        [
            json.dumps(_record(status="PASS", input_tokens=10, output_tokens=5, cost_usd=0.01, duration_s=1.0)),
            json.dumps(_record(status="FAIL", input_tokens=20, output_tokens=None, cost_usd=None, duration_s=3.0)),
            json.dumps(_record(status="BLOCKED", input_tokens=None, output_tokens=7, cost_usd=0.02, duration_s=2.0)),
            json.dumps(_record(agent="implementer", status="PASS", input_tokens=100, cost_usd=None, duration_s=5.0)),
        ],
    )

    records, malformed = usage_report.load_records(log, since=None)
    assert malformed == 0
    report = usage_report.aggregate(records)

    explorer = report["codebase-explorer"]
    assert explorer["calls"] == 3
    assert explorer["pass"] == 1
    assert explorer["fail"] == 1
    assert explorer["blocked"] == 1
    assert explorer["input_tokens"] == 30  # 10 + 20, None skipped
    assert explorer["output_tokens"] == 12  # 5 + 7, None skipped
    assert explorer["cost_usd"] == 0.03  # 0.01 + 0.02, None skipped
    assert explorer["median_duration_s"] == 2.0  # median of [1.0, 3.0, 2.0]

    implementer = report["implementer"]
    assert implementer["calls"] == 1
    assert implementer["input_tokens"] == 100
    assert implementer["cost_usd"] is None  # only value present was None

    total = report["TOTAL"]
    assert total["calls"] == 4
    assert total["pass"] == 2
    assert total["fail"] == 1
    assert total["blocked"] == 1
    assert total["input_tokens"] == 130


def test_since_filters_by_timestamp(tmp_path: Path) -> None:
    log = tmp_path / "usage.jsonl"
    write_log(
        log,
        [
            json.dumps(_record(ts="2026-01-01T00:00:00+00:00")),
            json.dumps(_record(ts="2026-01-05T12:00:00+00:00")),
            json.dumps(_record(ts="2025-12-31T23:59:59+00:00")),
        ],
    )

    since = usage_report.parse_since("2026-01-01")
    records, malformed = usage_report.load_records(log, since=since)

    assert malformed == 0
    assert len(records) == 2
    assert all(r["ts"] >= "2026-01-01" for r in records)


def test_invalid_since_raises_system_exit() -> None:
    try:
        usage_report.parse_since("not-a-date")
    except SystemExit as exc:
        assert "invalid --since" in str(exc)
    else:
        raise AssertionError("expected SystemExit for a malformed --since date")


def test_main_json_output_reports_malformed_count(tmp_path: Path, capsys) -> None:
    log = tmp_path / "usage.jsonl"
    write_log(log, [json.dumps(_record()), "garbage"])

    exit_code = usage_report.main(["--file", str(log), "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert exit_code == 0
    assert payload["malformed_lines"] == 1
    assert "codebase-explorer" in payload["agents"]
    assert "TOTAL" in payload["agents"]


def test_main_table_output_handles_empty_log(tmp_path: Path, capsys) -> None:
    log = tmp_path / "usage.jsonl"

    exit_code = usage_report.main(["--file", str(log)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "no usage records found" in out


def test_main_table_output_lists_agents_and_total(tmp_path: Path, capsys) -> None:
    log = tmp_path / "usage.jsonl"
    write_log(log, [json.dumps(_record()), json.dumps(_record(agent="implementer"))])

    exit_code = usage_report.main(["--file", str(log)])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "codebase-explorer" in out
    assert "implementer" in out
    assert "TOTAL" in out
