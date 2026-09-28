"""Project-agnostic behavior of tools/agents/delegate.py.

These tests guard the harness against re-acquiring project-specific
defaults: no test suite is built in, suites only come from a project's own
tools/agents/project.json, and the shipped template makes no assumption
about a project's Python tooling (no .venv/, no uv, no ruff).
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "tools" / "agents" / "delegate.py"


def _load_delegate():
    """Import a fresh, independent copy of delegate.py for isolation."""
    spec = importlib.util.spec_from_file_location("delegate_portability", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _init_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_builtin_canonical_test_commands_is_empty() -> None:
    fresh = _load_delegate()
    assert fresh.CANONICAL_TEST_COMMANDS == {}


def test_shipped_project_json_has_no_venv_assumption() -> None:
    config = json.loads(
        (_ROOT / "tools" / "agents" / "project.json").read_text(encoding="utf-8")
    )
    assert all(".venv" not in command for command in config["test_commands"].values())


def test_suites_come_from_project_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    fresh = _load_delegate()
    repo = _init_repo(tmp_path)
    config_dir = repo / "tools" / "agents"
    config_dir.mkdir(parents=True)
    config_dir.joinpath("project.json").write_text(
        json.dumps({"test_commands": {"smoke": "npm run smoke"}}), encoding="utf-8"
    )

    # orchestrator is enough to exercise the project.json load: it is
    # rejected right after that block, before spawning anything.
    exit_code = fresh.main(["--agent", "orchestrator", "--root", str(repo)])
    capsys.readouterr()

    assert exit_code == 1
    assert fresh.CANONICAL_TEST_COMMANDS == {"smoke": "npm run smoke"}


def test_unknown_test_suite_is_blocked_and_names_project_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    fresh = _load_delegate()
    repo = _init_repo(tmp_path)
    config_dir = repo / "tools" / "agents"
    config_dir.mkdir(parents=True)
    config_dir.joinpath("project.json").write_text(
        json.dumps({"test_commands": {"smoke": "npm run smoke"}}), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("run tests"))

    exit_code = fresh.main(
        ["--agent", "verifier", "--test-suite", "does-not-exist", "--root", str(repo)]
    )
    out = json.loads(capsys.readouterr().out.strip())

    assert exit_code == 1
    assert out["status"] == "BLOCKED"
    assert "does-not-exist" in out["response"]
    assert "tools/agents/project.json" in out["response"]


def test_missing_project_json_blocks_test_suite_and_names_project_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    fresh = _load_delegate()
    repo = _init_repo(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO("run tests"))

    exit_code = fresh.main(["--agent", "verifier", "--test-suite", "unit", "--root", str(repo)])
    out = json.loads(capsys.readouterr().out.strip())

    assert exit_code == 1
    assert out["status"] == "BLOCKED"
    assert "tools/agents/project.json" in out["response"]
