"""Gate tests for the harness instruction docs (AGENTS.md, the multi-agent
skill and its references, and the agents/ operations README).

These enforce the progressive-disclosure contract: AGENTS.md stays a small
always-loaded core, per-role detail lives in the multi-agent skill and its
references, model identity is looked up in tools/agents/agents.json instead
of being duplicated (and drifting) across prose, and no mention of the
private project this harness was extracted from leaks into shipped docs.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1]
FILES_ROOT = HARNESS / "files"
AGENTS_MD = FILES_ROOT / "AGENTS.md"
SKILL_DIR = FILES_ROOT / ".agents" / "skills" / "multi-agent"
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
README_MD = FILES_ROOT / "tools" / "agents" / "README.md"
AGENTS_JSON = FILES_ROOT / "tools" / "agents" / "agents.json"

# Files that carry the normative, always-checked prose: the compact core,
# the skill entry point, its references, and the operations README.
DOC_FILES = [AGENTS_MD, SKILL_MD, README_MD, *sorted(REFERENCES_DIR.glob("*.md"))]

# Name of the private project this harness was extracted from, spelled
# indirectly so this file passes its own sweep. The sweep covers the whole
# repo except vendored third-party skills (upstream content that names an
# unrelated product) and git/tool caches.
PRIVATE_PROJECT = "".join(("h", "e", "r", "m", "e", "s"))
SWEEP_SKIP_DIRS = {".git", "skills", "__pycache__", ".pytest_cache"}


def _swept(path: Path) -> bool:
    relative = path.relative_to(HARNESS)
    return not SWEEP_SKIP_DIRS.intersection(relative.parts[:-1] or ())


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_agents_md_is_compact() -> None:
    text = _read(AGENTS_MD)
    lines = text.splitlines()
    assert len(lines) <= 220, f"AGENTS.md has {len(lines)} lines, budget is 220"
    assert len(text) <= 11_000, f"AGENTS.md has {len(text)} chars, budget is 11000"


def test_no_model_ids_or_display_names_leak_into_prose() -> None:
    roster = json.loads(AGENTS_JSON.read_text(encoding="utf-8"))
    blob = "\n".join(_read(path) for path in DOC_FILES)
    leaks = []
    for role, config in roster.items():
        for key in ("model", "requested_model"):
            value = config.get(key)
            if value and value in blob:
                leaks.append(f"{role}.{key}={value!r}")
    assert not leaks, (
        "model id / display name strings leaked into docs (roles must be "
        f"referenced by name, models resolved via agents.json): {leaks}"
    )


def test_every_role_is_documented() -> None:
    roster = json.loads(AGENTS_JSON.read_text(encoding="utf-8"))
    blob = "\n".join(_read(path) for path in (SKILL_MD, *sorted(REFERENCES_DIR.glob("*.md"))))
    missing = [role for role in roster if role not in blob]
    assert not missing, f"roles missing from SKILL.md/references: {missing}"


def test_no_pasted_link_artifacts() -> None:
    pattern = re.compile(r"\[[^\]]*\]\(https?://[^)]*\)")
    offenders = []
    for path in DOC_FILES:
        for lineno, line in enumerate(_read(path).splitlines(), start=1):
            for match in pattern.finditer(line):
                url = match.group(0)
                # A pasted-link artifact is a relative file reference that
                # got wrapped in http(s):// by mistake, e.g.
                # [COMPLEXIDADE.md](http://COMPLEXIDADE.md). Flag any link
                # whose "domain" position is actually a bare filename.
                inner = re.search(r"\((https?://)([^)]*)\)", url)
                if inner and re.match(r"^[\w.-]+\.(md|json|toml|py)(#.*)?$", inner.group(2)):
                    offenders.append(f"{path}:{lineno}: {url}")
    assert not offenders, f"pasted-link artifacts found: {offenders}"


def test_referenced_relative_paths_exist() -> None:
    pattern = re.compile(r"`((?:tools|task|docs|\.agents)/[^`]*)`")
    missing = []
    for path in (AGENTS_MD, SKILL_MD, *sorted(REFERENCES_DIR.glob("*.md"))):
        for match in pattern.finditer(_read(path)):
            relative = match.group(1)
            if relative.startswith(("artifacts/", ".harness/")):
                continue
            if "<" in relative or ">" in relative:
                continue  # template placeholder, not a real path
            if not (FILES_ROOT / relative).exists():
                missing.append(f"{path.name}: {relative}")
    assert not missing, f"backticked paths that do not exist under files/: {missing}"


def test_no_private_project_mentions_in_repo() -> None:
    offenders = []
    for path in sorted(HARNESS.rglob("*")):
        if not path.is_file() or not _swept(path):
            continue
        if PRIVATE_PROJECT in path.relative_to(HARNESS).as_posix().lower():
            offenders.append(str(path.relative_to(HARNESS)))
            continue
        try:
            text = _read(path)
        except UnicodeDecodeError:
            continue
        if re.search(PRIVATE_PROJECT, text, re.IGNORECASE):
            offenders.append(str(path.relative_to(HARNESS)))
    assert not offenders, f"private project name found in: {offenders}"


def test_skill_frontmatter_is_valid() -> None:
    text = _read(SKILL_MD)
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    end = text.index("\n---", 4)
    frontmatter = text[4:end]
    fields = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    assert fields.get("name") == "multi-agent"
    assert fields.get("description"), "SKILL.md frontmatter needs a non-empty description"


@pytest.mark.skipif(sys.platform == "win32", reason="harness is POSIX only")
def test_install_exposes_references_via_no_skills(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)

    result = subprocess.run(
        [sys.executable, str(HARNESS / "install.py"), str(target), "--no-skills"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    installed_references = target / ".agents" / "skills" / "multi-agent" / "references"
    assert installed_references.is_dir()
    assert {p.name for p in installed_references.glob("*.md")} == {
        p.name for p in REFERENCES_DIR.glob("*.md")
    }

    link = target / ".claude" / "skills" / "multi-agent"
    assert link.is_symlink()
    resolved = (link / "SKILL.md").resolve()
    assert resolved == (target / ".agents" / "skills" / "multi-agent" / "SKILL.md").resolve()
    assert (link / "references").is_dir()
