from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


HARNESS = Path(__file__).resolve().parents[1]
INSTALL = HARNESS / "install.sh"
BEGIN = "<!-- portable-agent-harness:begin -->"
END = "<!-- portable-agent-harness:end -->"


def make_collection(root: Path, collection: str, skill: str) -> Path:
    checkout = root / collection
    category = Path("engineering") if collection == "mattpocock-skills" else Path()
    skill_dir = checkout / "skills" / category / skill
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill}\n---\n\nInstructions for {skill}.\n",
        encoding="utf-8",
    )
    (skill_dir / "references" / "guide.md").write_text(
        f"resource for {skill}\n", encoding="utf-8"
    )
    (skill_dir / "__pycache__").mkdir()
    (skill_dir / "__pycache__" / "ignored.pyc").write_bytes(b"cache")
    (skill_dir / ".DS_Store").write_bytes(b"finder")
    return checkout


@pytest.fixture
def skill_sources(tmp_path: Path) -> tuple[Path, Path]:
    source_root = tmp_path / "sources"
    return (
        make_collection(source_root, "mattpocock-skills", "typescript-testing"),
        make_collection(source_root, "superpowers", "executing-plans"),
    )


def run_install(
    target: Path,
    sources: tuple[Path, ...] | tuple[Path, Path],
    *extra: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["bash", str(INSTALL), str(target)]
    for source in sources:
        command.extend(("--skills-source", str(source)))
    command.extend(extra)
    env = os.environ.copy()
    env["HOME"] = str(target.parent / "empty-home")
    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=True,
        env=env,
    )


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def test_install_preserves_instructions_and_exposes_complete_skills_idempotently(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    target = tmp_path / "project"
    target.mkdir()
    (target / "AGENTS.md").write_text("project agents\n", encoding="utf-8")
    (target / "CLAUDE.md").write_text("project claude\n", encoding="utf-8")

    first = run_install(target, skill_sources)
    assert first.returncode == 0

    for instruction, original in (
        ("AGENTS.md", "project agents\n"),
        ("CLAUDE.md", "project claude\n"),
    ):
        installed = (target / instruction).read_text(encoding="utf-8")
        assert installed.startswith(original)
        assert installed.count(BEGIN) == 1
        assert installed.count(END) == 1
        assert (HARNESS / "files" / "AGENTS.md").read_text(encoding="utf-8") in installed

    for collection, skill in (
        ("mattpocock-skills", "typescript-testing"),
        ("superpowers", "executing-plans"),
    ):
        category = Path("engineering") if collection == "mattpocock-skills" else Path()
        vendored = target / ".harness" / "skills" / collection / category / skill
        assert (vendored / "references" / "guide.md").is_file()
        assert not (vendored / "__pycache__").exists()
        assert not (vendored / ".DS_Store").exists()
        for consumer in (".agents", ".claude"):
            exposed = target / consumer / "skills" / skill
            assert exposed.is_symlink()
            assert not os.path.isabs(os.readlink(exposed))
            assert exposed.resolve() == vendored.resolve()

    claude_workflow = target / ".claude" / "skills" / "multi-agent"
    assert claude_workflow.is_symlink()
    assert claude_workflow.resolve() == (
        target / ".agents" / "skills" / "multi-agent"
    ).resolve()

    assert not (target / ".codex" / "config.toml").exists()
    assert not any(target.rglob("__pycache__"))
    manifest = json.loads((target / ".harness" / "manifest.json").read_text())
    assert set(manifest["skill_sources"]) == {
        "mattpocock-skills",
        "superpowers",
    }
    snapshot = {
        path.relative_to(target).as_posix(): (
            os.readlink(path) if path.is_symlink() else path.read_bytes()
        )
        for path in target.rglob("*")
        if path.is_file() or path.is_symlink()
    }

    second = run_install(target, skill_sources)
    assert second.returncode == 0
    assert snapshot == {
        path.relative_to(target).as_posix(): (
            os.readlink(path) if path.is_symlink() else path.read_bytes()
        )
        for path in target.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def test_collision_is_rejected_before_any_file_is_written(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    target = tmp_path / "project"
    collision = target / "tools" / "agents" / "delegate.py"
    collision.parent.mkdir(parents=True)
    collision.write_text("user owned\n", encoding="utf-8")

    result = run_install(target, skill_sources, check=False)

    assert result.returncode != 0
    assert "collision" in result.stderr.lower()
    assert collision.read_text(encoding="utf-8") == "user owned\n"
    assert not (target / ".harness").exists()
    assert not (target / "AGENTS.md").exists()


def test_modified_managed_file_blocks_reinstall_without_partial_update(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    target = tmp_path / "project"
    target.mkdir()
    run_install(target, skill_sources)
    managed = target / "tools" / "agents" / "delegate.py"
    managed.write_text("locally modified\n", encoding="utf-8")
    agents_before = (target / "AGENTS.md").read_bytes()

    result = run_install(target, skill_sources, check=False)

    assert result.returncode != 0
    assert "modified" in result.stderr.lower()
    assert managed.read_text(encoding="utf-8") == "locally modified\n"
    assert (target / "AGENTS.md").read_bytes() == agents_before


def test_dry_run_validates_but_writes_nothing(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    target = tmp_path / "project"
    target.mkdir()

    result = run_install(target, skill_sources, "--dry-run")

    assert "dry-run" in result.stdout.lower()
    assert list(target.iterdir()) == []


def test_requires_both_upstream_collections_with_actionable_error(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    target = tmp_path / "project"
    target.mkdir()

    result = run_install(target, (skill_sources[0],), check=False)

    assert result.returncode != 0
    assert "superpowers" in result.stderr
    assert "--skills-source" in result.stderr
    assert list(target.iterdir()) == []


def test_rejects_destination_symlink_that_could_escape_target(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    target = tmp_path / "project"
    outside = tmp_path / "outside"
    target.mkdir()
    outside.mkdir()
    (target / "tools").symlink_to(outside, target_is_directory=True)

    result = run_install(target, skill_sources, check=False)

    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert list(outside.iterdir()) == []
    assert not (target / ".harness").exists()


def test_rejects_target_directory_symlink(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    actual = tmp_path / "actual-project"
    target = tmp_path / "project-link"
    actual.mkdir()
    target.symlink_to(actual, target_is_directory=True)

    result = run_install(target, skill_sources, check=False)

    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert list(actual.iterdir()) == []


def test_git_root_and_worktree_use_git_resolved_local_exclude(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git("init", cwd=repository)
    git("config", "user.email", "test@example.invalid", cwd=repository)
    git("config", "user.name", "Test", cwd=repository)
    (repository / "AGENTS.md").write_text("tracked instructions\n", encoding="utf-8")
    git("add", "AGENTS.md", cwd=repository)
    git("commit", "-m", "initial", cwd=repository)

    run_install(repository, skill_sources)
    exclude = Path(git("rev-parse", "--git-path", "info/exclude", cwd=repository))
    if not exclude.is_absolute():
        exclude = repository / exclude
    exclude_text = exclude.read_text(encoding="utf-8")
    assert "/.harness/" in exclude_text
    assert "/tools/agents/" in exclude_text
    assert "/AGENTS.md" not in exclude_text
    assert git("ls-files", "AGENTS.md", cwd=repository) == "AGENTS.md"

    branch = tmp_path / "linked-worktree"
    git("worktree", "add", "-b", "test-worktree", str(branch), cwd=repository)
    run_install(branch, skill_sources)
    worktree_exclude = Path(git("rev-parse", "--git-path", "info/exclude", cwd=branch))
    if not worktree_exclude.is_absolute():
        worktree_exclude = branch / worktree_exclude
    assert worktree_exclude.resolve() == exclude.resolve()
    assert "/.agents/skills/" in worktree_exclude.read_text(encoding="utf-8")
    assert git("ls-files", "AGENTS.md", cwd=branch) == "AGENTS.md"


def test_malformed_git_exclude_is_rejected_before_payload_writes(
    tmp_path: Path, skill_sources: tuple[Path, Path]
) -> None:
    target = tmp_path / "repository"
    target.mkdir()
    git("init", cwd=target)
    exclude = Path(git("rev-parse", "--git-path", "info/exclude", cwd=target))
    if not exclude.is_absolute():
        exclude = target / exclude
    exclude.write_text("# portable-agent-harness:begin\n", encoding="utf-8")

    result = run_install(target, skill_sources, check=False)

    assert result.returncode != 0
    assert "malformed" in result.stderr.lower()
    assert exclude.read_text(encoding="utf-8") == "# portable-agent-harness:begin\n"
    assert not (target / ".harness").exists()
    assert not (target / "AGENTS.md").exists()


def test_no_skills_installs_payload_without_vendoring(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    # Skills locais pre-existentes (gerenciadas pelo projeto) nao podem colidir.
    (target / ".agents" / "skills" / "tdd").mkdir(parents=True)
    (target / ".agents" / "skills" / "tdd" / "SKILL.md").write_text("local tdd\n")

    result = run_install(target, (), "--no-skills")

    assert result.returncode == 0, result.stderr
    assert (target / "tools" / "agents" / "delegate.py").is_file()
    assert (target / "tools" / "agents" / "project.json").is_file()
    assert (target / ".agents" / "skills" / "multi-agent" / "SKILL.md").is_file()
    assert (target / ".claude" / "skills" / "multi-agent").is_symlink()
    assert not (target / ".harness" / "skills").exists()
    assert (target / ".agents" / "skills" / "tdd" / "SKILL.md").read_text() == "local tdd\n"
    manifest = json.loads((target / ".harness" / "manifest.json").read_text())
    assert manifest["skill_sources"] == {}


def test_claude_instructions_can_target_local_file(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    git("init", "-q", cwd=target)
    (target / "CLAUDE.md").write_text("project claude\n", encoding="utf-8")
    git("add", "CLAUDE.md", cwd=target)
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init", cwd=target)

    result = run_install(target, (), "--no-skills", "--claude-instructions", "CLAUDE.local.md")

    assert result.returncode == 0, result.stderr
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == "project claude\n"
    local = (target / "CLAUDE.local.md").read_text(encoding="utf-8")
    assert local.count(BEGIN) == 1 and local.count(END) == 1
    exclude = (target / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert "/CLAUDE.local.md" in exclude
    assert "/AGENTS.md" in exclude
    assert "/CLAUDE.md" not in exclude.replace("/CLAUDE.local.md", "")
    assert git("status", "--porcelain", cwd=target) == ""


SEEDS = (Path("tools/agents/project.json"), Path("task/COMPLEXIDADE.md"))


def test_seed_files_are_created_once_and_preserved_on_reinstall(tmp_path: Path) -> None:
    target = tmp_path / "project"
    target.mkdir()
    run_install(target, (), "--no-skills")
    for seed in SEEDS:
        assert (target / seed).is_file()
        (target / seed).write_text(f"adapted {seed.name}\n", encoding="utf-8")

    result = run_install(target, (), "--no-skills", check=False)

    assert result.returncode == 0, result.stderr
    for seed in SEEDS:
        assert (target / seed).read_text(encoding="utf-8") == f"adapted {seed.name}\n"
    manifest = json.loads((target / ".harness" / "manifest.json").read_text())
    assert not {s.as_posix() for s in SEEDS} & set(manifest["entries"])


def test_preexisting_seed_files_do_not_collide(tmp_path: Path) -> None:
    target = tmp_path / "project"
    for seed in SEEDS:
        (target / seed).parent.mkdir(parents=True, exist_ok=True)
        (target / seed).write_text("project owned\n", encoding="utf-8")

    result = run_install(target, (), "--no-skills", check=False)

    assert result.returncode == 0, result.stderr
    for seed in SEEDS:
        assert (target / seed).read_text(encoding="utf-8") == "project owned\n"


def test_legacy_manifest_seed_entries_are_neither_blocking_nor_deleted(
    tmp_path: Path,
) -> None:
    target = tmp_path / "project"
    target.mkdir()
    run_install(target, (), "--no-skills")
    manifest_path = target / ".harness" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for seed in SEEDS:
        manifest["entries"][seed.as_posix()] = {"type": "file", "sha256": "0" * 64}
        (target / seed).write_text("adapted\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest))

    result = run_install(target, (), "--no-skills", check=False)

    assert result.returncode == 0, result.stderr
    for seed in SEEDS:
        assert (target / seed).read_text(encoding="utf-8") == "adapted\n"
