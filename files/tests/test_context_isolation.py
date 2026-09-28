"""Regression tests for sub-agent context isolation.

Sub-agents must never inherit the orchestrator's project instruction files
(CLAUDE.md, CLAUDE.local.md, AGENTS.md): the handoff prompt already carries
whatever context a role needs, and the orchestrator-only manual is large
enough that leaking it would waste every sub-agent's budget. The unit tests
below check the argv our builder functions produce; the opt-in live test
below that actually spawns the real CLIs and confirms planted facts from
those files do not leak into a sub-agent's answer.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "tools" / "agents" / "delegate.py"
_SPEC = importlib.util.spec_from_file_location("delegate", _SCRIPT)
assert _SPEC and _SPEC.loader
delegate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(delegate)


# --- Unit tests: argv shape only, no process spawned. ----------------------


def test_codex_argv_disables_project_doc_loading() -> None:
    argv = delegate.build_codex_argv(
        model="gpt-6-luna",
        reasoning_effort="low",
        sandbox_mode="read-only",
        last_message_path="/tmp/last-message.txt",
    )
    assert "project_doc_max_bytes=0" in argv
    # It must be paired with its own -c, not merged into another override.
    idx = argv.index("project_doc_max_bytes=0")
    assert argv[idx - 1] == "-c"


def test_claude_argv_uses_restricted_not_bare() -> None:
    argv = delegate.build_claude_argv(
        model="claude-haiku-4-5",
        effort="low",
        tool_names=[],
        allowed_tools=[],
        permission_mode="dontAsk",
    )
    assert "--restricted" in argv
    assert "--bare" not in argv


def test_agy_argv_safety_flags_unchanged() -> None:
    read_only = delegate.build_agy_argv(
        model="gemini-3.8-flash-medium", writes=False, timeout=120, prompt="hello"
    )
    assert "--disable-slash-commands" in read_only
    assert "--sandbox" in read_only

    writer = delegate.build_agy_argv(
        model="gemini-3.8-flash-medium", writes=True, timeout=120, prompt="hello"
    )
    assert "--disable-slash-commands" in writer
    # Unchanged existing behaviour: a writer role drops --sandbox.
    assert "--sandbox" not in writer


# --- Opt-in live test: spawns the real CLIs. --------------------------------

_PLANTED_FACTS = {
    "CLAUDE.md": "Project fact: the deployment region is REGION-ALPHA-7042.",
    "CLAUDE.local.md": "Project fact: the database name is DBNAME-BETA-9183.",
    "AGENTS.md": "Project fact: the team mascot is MASCOT-GAMMA-3355.",
}
_SECRET_TOKENS = ["REGION-ALPHA-7042", "DBNAME-BETA-9183", "MASCOT-GAMMA-3355"]
_LIVE_PROMPT = (
    "Without using tools, from instructions already in your context, what is "
    "the deployment region / database name / team mascot? UNKNOWN if absent."
)


def _make_planted_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "planted-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    for filename, fact in _PLANTED_FACTS.items():
        (repo / filename).write_text(fact + "\n", encoding="utf-8")
    return repo


def _assert_no_leak(answer: str) -> None:
    lowered = answer.lower()
    leaked = [token for token in _SECRET_TOKENS if token.lower() in lowered]
    assert not leaked, f"planted fact(s) leaked into sub-agent answer: {leaked}\n{answer!r}"


def _extract_claude_result(stdout_text: str) -> tuple[bool, str]:
    """Pull the final result text out of --output-format stream-json.

    Deliberately independent of delegate.parse_claude_stream (another
    worker is editing that function concurrently): this only needs the raw
    answer text for the leak check, not the harness's pass/fail contract.
    """
    is_error = True
    result = ""
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line:
            continue
        event = json.loads(line)
        if event.get("type") == "result":
            is_error = bool(event.get("is_error", True))
            result = event.get("result", "")
    return not is_error, result


@pytest.mark.skipif(
    os.environ.get("HARNESS_LIVE") != "1",
    reason="live CLI test; set HARNESS_LIVE=1 to run",
)
def test_live_claude_and_codex_do_not_leak_project_instructions(
    tmp_path: Path,
) -> None:
    repo = _make_planted_repo(tmp_path)

    # -- Claude: prompt goes via stdin because --tools is variadic. --
    claude_model = os.environ.get("HARNESS_LIVE_CLAUDE_MODEL", "haiku")
    claude_argv = delegate.build_claude_argv(
        model=claude_model,
        effort="low",
        tool_names=[],
        allowed_tools=[],
        permission_mode="dontAsk",
    )
    claude_proc = subprocess.run(
        claude_argv,
        cwd=repo,
        input=_LIVE_PROMPT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert claude_proc.returncode == 0, claude_proc.stderr
    claude_ok, claude_answer = _extract_claude_result(claude_proc.stdout)
    assert claude_ok and claude_answer, (claude_proc.stdout, claude_proc.stderr)
    _assert_no_leak(claude_answer)

    # -- Codex: prompt goes via stdin ("-" as the final argv entry). --
    codex_model = os.environ.get("HARNESS_LIVE_CODEX_MODEL", "gpt-6-luna")
    with tempfile.TemporaryDirectory(prefix="harness-live-codex-") as workdir:
        last_message = Path(workdir) / "last-message.txt"
        codex_argv = delegate.build_codex_argv(
            model=codex_model,
            reasoning_effort="low",
            sandbox_mode="read-only",
            last_message_path=str(last_message),
        )
        codex_proc = subprocess.run(
            codex_argv,
            cwd=repo,
            input=_LIVE_PROMPT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert codex_proc.returncode == 0, codex_proc.stderr
        codex_answer = last_message.read_text(encoding="utf-8") if last_message.exists() else ""
    assert codex_answer.strip(), "codex produced no final message"
    _assert_no_leak(codex_answer)
