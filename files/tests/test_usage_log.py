"""Tests for delegate.py's usage.jsonl logging (tasks: log one line per
invocation, never touch the printed JSON contract, never change the
verdict on a logging failure, honor HARNESS_USAGE_LOG=0).
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "tools" / "agents" / "delegate.py"
_SPEC = importlib.util.spec_from_file_location("delegate_usage_log", _SCRIPT)
assert _SPEC and _SPEC.loader
delegate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(delegate)


def _write_fake_cli(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env python3\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if os.name != "posix":
        pytest.skip("requires POSIX process execution")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return bin_dir


@pytest.fixture(autouse=True)
def isolated_repo_root(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point delegate at a throwaway repo root for every test in this file.

    This is the isolation that matters here: without it, the usage log
    would land in this checkout's own files/.harness/usage.jsonl (see the
    equivalent hermetic_skill_cache fixture in test_agent_delegation.py,
    which points _REPO_ROOT at that same files/ tree for its own tests).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.delenv("HARNESS_USAGE_LOG", raising=False)
    monkeypatch.setattr(delegate, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(delegate, "ROLE_SKILLS", dict(delegate.ROLE_SKILLS))
    cache = tmp_path_factory.mktemp("plugin-cache")
    for specs in delegate.ROLE_SKILLS.values():
        for spec in specs:
            plugin, _, relative = spec.partition("/")
            target = cache / plugin / "0.0.0" / "skills" / relative
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(f"stub for {spec}", encoding="utf-8")
    monkeypatch.setattr(delegate, "PLUGIN_CACHE_ROOT", cache)
    return repo_root


def usage_log_path(repo_root: Path) -> Path:
    return repo_root / ".harness" / "usage.jsonl"


def read_usage_records(repo_root: Path) -> list[dict[str, Any]]:
    path = usage_log_path(repo_root)
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    stdin_text: str = "do the thing",
) -> tuple[dict[str, Any], int]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    exit_code = delegate.main(argv)
    out = capsys.readouterr().out.strip()
    return json.loads(out), exit_code


def _claude_success_body(model: str, *, extra_result_fields: str = "") -> str:
    return (
        "import json, sys\n"
        f"model = {model!r}\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init', 'model': model}))\n"
        "print(json.dumps({'type': 'assistant', "
        "'message': {'model': model, 'content': 'ok'}}))\n"
        "print(json.dumps({\n"
        "    'type': 'result', 'is_error': False, 'subtype': 'success',\n"
        "    'result': 'done', 'permission_denials': [], "
        "'session_id': 's1',\n"
        "    'duration_ms': 12, 'num_turns': 1,\n"
        f"    {extra_result_fields}\n"
        "}))\n"
        "sys.stdin.read()\n"
    )


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_claude_pass_logs_tokens_cost_and_hashed_task(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_bin: Path,
    isolated_repo_root: Path,
) -> None:
    body = _claude_success_body(
        "claude-sonnet-5-5",
        extra_result_fields=(
            "'usage': {'input_tokens': 100, 'output_tokens': 50, "
            "'cache_creation_input_tokens': 5, 'cache_read_input_tokens': 7}, "
            "'total_cost_usd': 0.0123,"
        ),
    )
    _write_fake_cli(fake_bin / "claude", body)
    task_text = "look at the auth module"

    result, exit_code = _run_main(
        monkeypatch, capsys, ["--agent", "codebase-explorer"], stdin_text=task_text
    )

    assert exit_code == 0
    assert result["status"] == "PASS"
    # Printed contract is unchanged: total_cost_usd must never appear there.
    assert "total_cost_usd" not in result
    assert result["usage"]["input_tokens"] == 100

    records = read_usage_records(isolated_repo_root)
    assert len(records) == 1
    record = records[0]
    assert record["agent"] == "codebase-explorer"
    assert record["provider"] == "Claude Code CLI"
    assert record["model"] == "claude-sonnet-5-5"
    assert record["status"] == "PASS"
    assert record["smoke"] is False
    assert record["exit_code"] == 0
    assert isinstance(record["duration_s"], float) and record["duration_s"] >= 0
    assert record["input_tokens"] == 100
    assert record["output_tokens"] == 50
    assert record["cache_creation_tokens"] == 5
    assert record["cache_read_tokens"] == 7
    assert record["cost_usd"] == 0.0123
    assert record["task_chars"] == len(task_text)
    assert record["task_sha256"] == hashlib.sha256(task_text.encode("utf-8")).hexdigest()
    # The task text itself must never be persisted.
    assert task_text not in json.dumps(record)
    raw_line = usage_log_path(isolated_repo_root).read_text(encoding="utf-8")
    assert task_text not in raw_line


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_codex_pass_maps_provider_token_fields_and_cost_is_null(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_bin: Path,
    isolated_repo_root: Path,
) -> None:
    dump = fake_bin.parent / "argv.json"
    body = (
        "import sys, json\n"
        "argv = sys.argv\n"
        f"open({str(dump)!r}, 'w').write(json.dumps(argv))\n"
        "idx = argv.index('--output-last-message')\n"
        "open(argv[idx + 1], 'w').write('CODEX REPORT')\n"
        "print(json.dumps({'type': 'thread.started', 'thread_id': 't1'}))\n"
        "print(json.dumps({'type': 'turn.started'}))\n"
        # Field names evidenced from the codex binary's embedded
        # TurnCompletedEvent strings: input_tokens, cached_input_tokens,
        # cache_write_input_tokens, output_tokens, reasoning_output_tokens.
        "print(json.dumps({'type': 'turn.completed', 'usage': {"
        "'input_tokens': 200, 'cached_input_tokens': 40, "
        "'cache_write_input_tokens': 9, 'output_tokens': 80, "
        "'reasoning_output_tokens': 12}}))\n"
        "sys.stdin.read()\n"
    )
    _write_fake_cli(fake_bin / "codex", body)

    result, exit_code = _run_main(monkeypatch, capsys, ["--agent", "code-reviewer"])

    assert exit_code == 0
    assert result["status"] == "PASS"

    records = read_usage_records(isolated_repo_root)
    assert len(records) == 1
    record = records[0]
    assert record["provider"] == "Codex CLI"
    assert record["input_tokens"] == 200
    assert record["output_tokens"] == 80
    assert record["cache_read_tokens"] == 40
    assert record["cache_creation_tokens"] == 9
    # No USD cost field is present anywhere in `codex exec --json` output.
    assert record["cost_usd"] is None


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_agy_pass_uses_best_effort_aliases_and_cost_is_always_null(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_bin: Path,
    isolated_repo_root: Path,
) -> None:
    body = (
        "import json\n"
        "print(json.dumps({'conversation_id': 'c1', 'status': 'SUCCESS', "
        "'response': 'RESEARCH_OK', 'duration_seconds': 1.0, 'num_turns': 1, "
        "'model': 'gemini-3.8-flash-high', "
        "'usage': {'input_tokens': 10, 'output_tokens': 4, "
        "'cache_creation_input_tokens': 1, 'cache_read_input_tokens': 2}}))\n"
    )
    _write_fake_cli(fake_bin / "agy", body)

    result, exit_code = _run_main(monkeypatch, capsys, ["--agent", "researcher-primary"])

    assert exit_code == 0
    assert result["status"] == "PASS"

    records = read_usage_records(isolated_repo_root)
    assert len(records) == 1
    record = records[0]
    assert record["provider"] == "AGY"
    # AGY's usage payload shape is not documented anywhere in this wrapper
    # or its tests; these are best-effort aliases, verified here only
    # against our own fixture, not a real AGY run.
    assert record["input_tokens"] == 10
    assert record["output_tokens"] == 4
    assert record["cache_creation_tokens"] == 1
    assert record["cache_read_tokens"] == 2
    assert record["cost_usd"] is None


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_opt_out_env_var_disables_logging(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_bin: Path,
    isolated_repo_root: Path,
) -> None:
    _write_fake_cli(fake_bin / "claude", _claude_success_body("claude-sonnet-5-5"))
    monkeypatch.setenv("HARNESS_USAGE_LOG", "0")

    result, exit_code = _run_main(monkeypatch, capsys, ["--agent", "codebase-explorer"])

    assert exit_code == 0
    assert result["status"] == "PASS"
    assert not usage_log_path(isolated_repo_root).exists()


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_unwritable_log_dir_does_not_change_verdict_or_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_bin: Path,
    isolated_repo_root: Path,
) -> None:
    _write_fake_cli(fake_bin / "claude", _claude_success_body("claude-sonnet-5-5"))
    log_dir = usage_log_path(isolated_repo_root).parent
    log_dir.mkdir(parents=True)
    log_dir.chmod(0o500)
    monkeypatch.setattr(sys, "stdin", io.StringIO("do the thing"))
    try:
        exit_code = delegate.main(["--agent", "codebase-explorer"])
    finally:
        log_dir.chmod(0o700)
    # A single capsys.readouterr() call drains both streams at once; _run_main
    # already does this for stdout, so stderr is read here directly instead.
    captured = capsys.readouterr()
    result = json.loads(captured.out.strip())

    assert exit_code == 0
    assert result["status"] == "PASS"
    assert captured.err.count("usage log") <= 1
    assert "usage log" in captured.err


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_smoke_run_is_logged_with_smoke_true(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_bin: Path,
    isolated_repo_root: Path,
) -> None:
    _write_fake_cli(fake_bin / "claude", _claude_success_body("claude-sonnet-5-5"))

    result, exit_code = _run_main(monkeypatch, capsys, ["--agent", "implementer", "--smoke"])

    assert exit_code == 0
    records = read_usage_records(isolated_repo_root)
    assert len(records) == 1
    assert records[0]["smoke"] is True


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_early_blocked_role_is_logged_without_task_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated_repo_root: Path,
) -> None:
    roster = delegate.load_agents()
    roster["codebase-explorer"]["status"] = "BLOCKED"
    roster["codebase-explorer"]["reason"] = "disabled for maintenance"
    monkeypatch.setattr(delegate, "load_agents", lambda: roster)

    result, exit_code = _run_main(monkeypatch, capsys, ["--agent", "codebase-explorer"])

    assert exit_code == 1
    assert result["status"] == "BLOCKED"
    records = read_usage_records(isolated_repo_root)
    assert len(records) == 1
    record = records[0]
    assert record["status"] == "BLOCKED"
    assert record["input_tokens"] is None
    assert record["cost_usd"] is None
    # read_task() never ran for this early exit, so there is no task text.
    assert record["task_sha256"] is None
    assert record["task_chars"] == 0


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_malformed_provider_output_logs_fail_with_null_tokens(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_bin: Path,
    isolated_repo_root: Path,
) -> None:
    _write_fake_cli(fake_bin / "claude", "print('not json')")

    result, exit_code = _run_main(monkeypatch, capsys, ["--agent", "codebase-explorer"])

    assert result["status"] == "FAIL"
    records = read_usage_records(isolated_repo_root)
    assert len(records) == 1
    record = records[0]
    assert record["status"] == "FAIL"
    assert record["input_tokens"] is None
    assert record["cost_usd"] is None


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_two_invocations_append_two_well_formed_lines(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_bin: Path,
    isolated_repo_root: Path,
) -> None:
    _write_fake_cli(fake_bin / "claude", _claude_success_body("claude-sonnet-5-5"))

    _run_main(monkeypatch, capsys, ["--agent", "codebase-explorer"], stdin_text="first")
    _run_main(monkeypatch, capsys, ["--agent", "codebase-explorer"], stdin_text="second")

    raw_lines = [
        line
        for line in usage_log_path(isolated_repo_root).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(raw_lines) == 2
    for line in raw_lines:
        json.loads(line)  # each line is a single, complete JSON object


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX process execution")
def test_orchestrator_blocked_before_dispatch_is_logged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated_repo_root: Path,
) -> None:
    result, exit_code = _run_main(monkeypatch, capsys, ["--agent", "orchestrator"])

    assert exit_code == 1
    assert result["status"] == "BLOCKED"
    records = read_usage_records(isolated_repo_root)
    assert len(records) == 1
    assert records[0]["agent"] == "orchestrator"
    assert records[0]["status"] == "BLOCKED"
