#!/usr/bin/env python3
"""Install the portable agent harness into an existing project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Iterable


COLLECTIONS = ("mattpocock-skills", "superpowers")
BEGIN = "<!-- portable-agent-harness:begin -->"
END = "<!-- portable-agent-harness:end -->"
EXCLUDE_BEGIN = "# portable-agent-harness:begin"
EXCLUDE_END = "# portable-agent-harness:end"
MANIFEST_PATH = Path(".harness/manifest.json")
IGNORED_NAMES = {".DS_Store", "__pycache__"}
# Arquivos que o projeto deve adaptar: criados só se faltarem, nunca
# sobrescritos nem registrados no manifesto (reinstalar não os trava).
SEED_PATHS = frozenset({Path("tools/agents/project.json"), Path("task/COMPLEXIDADE.md")})


class InstallError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    return digest(path.read_bytes())


def ignored(relative: Path) -> bool:
    return any(part in IGNORED_NAMES for part in relative.parts)


def source_files(root: Path) -> Iterable[tuple[Path, Path]]:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ignored(relative):
            continue
        if path.is_symlink():
            raise InstallError(f"source contains unsupported symlink: {path}")
        if path.is_file():
            yield relative, path


def classify_source(raw: Path) -> tuple[str, Path]:
    path = raw.expanduser().resolve()
    if not path.is_dir():
        raise InstallError(f"skills source does not exist or is not a directory: {raw}")
    if path.name in COLLECTIONS and (path / "skills").is_dir():
        return path.name, path / "skills"
    if path.name == "skills" and path.parent.name in COLLECTIONS:
        return path.parent.name, path
    raise InstallError(
        f"cannot identify collection for {raw}; provide a {COLLECTIONS[0]} or "
        f"{COLLECTIONS[1]} checkout root (or its skills directory)"
    )


def discover_sources(explicit: list[Path]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for raw in explicit:
        collection, skills = classify_source(raw)
        previous = found.get(collection)
        if previous is not None and previous != skills:
            raise InstallError(f"multiple --skills-source values provided for {collection}")
        found[collection] = skills

    home = Path.home()
    for collection in COLLECTIONS:
        if collection in found:
            continue
        candidates: list[Path] = []
        for cache in (home / ".claude/plugins/cache", home / ".codex/plugins/cache"):
            if cache.is_dir():
                candidates.extend(cache.glob(f"*/{collection}/*/skills"))
        valid = sorted((p.resolve() for p in candidates if p.is_dir()), key=str)
        if valid:
            found[collection] = valid[-1]

    missing = [name for name in COLLECTIONS if name not in found]
    if missing:
        raise InstallError(
            f"missing required local skill collection(s): {', '.join(missing)}. "
            "No downloads are performed; install them in a Claude/Codex plugin "
            "cache or pass each checkout with --skills-source PATH."
        )
    return found


def skill_directories(
    skills_root: Path, collection: str
) -> dict[str, tuple[Path, Path]]:
    skills: dict[str, tuple[Path, Path]] = {}
    for descriptor in sorted(skills_root.rglob("SKILL.md")):
        skill_root = descriptor.parent
        relative = skill_root.relative_to(skills_root)
        if ignored(relative):
            continue
        for candidate in (skill_root, *skill_root.parents):
            if candidate == skills_root.parent:
                break
            if candidate.is_symlink():
                raise InstallError(f"source contains unsupported symlink: {candidate}")
        if skill_root.name in skills:
            raise InstallError(
                f"duplicate skill name in {collection}: {skill_root.name}"
            )
        skills[skill_root.name] = (relative, skill_root)
    if not skills:
        raise InstallError(f"{collection} has no skill directories in {skills_root}")
    return skills


def payload_files(harness_root: Path) -> dict[Path, tuple[bytes, int, str]]:
    desired: dict[Path, tuple[bytes, int, str]] = {}
    for relative, source in source_files(harness_root / "files"):
        if relative in (Path("AGENTS.md"), Path(".codex/config.toml")):
            continue
        desired[relative] = (
            source.read_bytes(),
            source.stat().st_mode & 0o777,
            f"payload:{relative.as_posix()}",
        )
    return desired


def build_desired(
    harness_root: Path, sources: dict[str, Path], collections: tuple[str, ...] = COLLECTIONS
) -> tuple[dict[Path, tuple[bytes, int, str]], dict[Path, str]]:
    regular = payload_files(harness_root)
    links: dict[Path, str] = {}
    claimed_skills: dict[str, str] = {}
    payload_skill_root = harness_root / "files/.agents/skills"
    if payload_skill_root.is_dir():
        for child in payload_skill_root.iterdir():
            if child.is_dir():
                claimed_skills[child.name] = "harness payload"
                destination = Path(".claude/skills") / child.name
                local_skill = Path(".agents/skills") / child.name
                links[destination] = os.path.relpath(local_skill, start=destination.parent)

    for collection in collections:
        for skill_name, (skill_relative, skill_root) in skill_directories(
            sources[collection], collection
        ).items():
            owner = claimed_skills.get(skill_name)
            if owner is not None:
                raise InstallError(
                    f"skill name collision: {skill_name} is supplied by both {owner} "
                    f"and {collection}"
                )
            claimed_skills[skill_name] = collection
            vendor_root = Path(".harness/skills") / collection / skill_relative
            for relative, source in source_files(skill_root):
                regular[vendor_root / relative] = (
                    source.read_bytes(),
                    source.stat().st_mode & 0o777,
                    f"skills:{collection}:{sources[collection]}",
                )
            for consumer in (Path(".agents/skills"), Path(".claude/skills")):
                destination = consumer / skill_name
                absolute_target = Path(".harness/skills") / collection / skill_relative
                links[destination] = os.path.relpath(absolute_target, start=destination.parent)

    overlap = set(regular).intersection(links)
    if overlap:
        raise InstallError(f"destination collision: {min(overlap).as_posix()}")
    return regular, links


def read_manifest(target: Path) -> dict | None:
    path = target / MANIFEST_PATH
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise InstallError(f"collision at {MANIFEST_PATH.as_posix()}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"invalid existing manifest: {exc}") from exc
    if data.get("version") != 1 or not isinstance(data.get("entries"), dict):
        raise InstallError("invalid existing manifest schema")
    return data


def check_no_ancestor_symlinks(target: Path, relative: Path, allow_leaf: bool) -> None:
    current = target
    for index, part in enumerate(relative.parts):
        current = current / part
        if current.is_symlink():
            is_leaf = index == len(relative.parts) - 1
            if allow_leaf and is_leaf:
                return
            raise InstallError(f"unsafe destination symlink: {current}")


def managed_text(instructions: str) -> str:
    return f"{BEGIN}\n{instructions.rstrip()}\n{END}"


def inspect_instruction(
    target: Path, name: str, desired_block: str, old_block_hash: str | None
) -> str:
    relative = Path(name)
    check_no_ancestor_symlinks(target, relative, allow_leaf=False)
    path = target / relative
    if not path.exists():
        return desired_block + "\n"
    if not path.is_file():
        raise InstallError(f"collision at {name}")
    existing = path.read_text(encoding="utf-8")
    begin_count, end_count = existing.count(BEGIN), existing.count(END)
    if begin_count == end_count == 0:
        separator = "" if not existing or existing.endswith("\n\n") else "\n"
        return existing + separator + desired_block + "\n"
    if begin_count != 1 or end_count != 1:
        raise InstallError(f"malformed managed block in {name}")
    start = existing.index(BEGIN)
    finish = existing.index(END, start) + len(END)
    actual_block = existing[start:finish]
    if old_block_hash is None or digest(actual_block.encode()) != old_block_hash:
        if actual_block != desired_block:
            raise InstallError(f"modified managed block in {name}")
    return existing[:start] + desired_block + existing[finish:]


def preflight(
    target: Path,
    regular: dict[Path, tuple[bytes, int, str]],
    links: dict[Path, str],
    previous: dict | None,
    desired_block: str,
    instruction_files: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md"),
) -> tuple[dict[str, str], set[Path]]:
    old_entries = previous["entries"] if previous else {}
    old_block_hash = previous.get("managed_block_hash") if previous else None
    instruction_outputs = {
        name: inspect_instruction(target, name, desired_block, old_block_hash)
        for name in instruction_files
    }
    desired_paths = set(regular) | set(links)

    for relative in regular:
        check_no_ancestor_symlinks(target, relative, allow_leaf=False)
        destination = target / relative
        if not destination.exists() or relative in SEED_PATHS:
            continue
        old = old_entries.get(relative.as_posix())
        if old is None:
            raise InstallError(f"collision at {relative.as_posix()}")
        if not destination.is_file() or old.get("type") != "file":
            raise InstallError(f"modified managed path: {relative.as_posix()}")
        if file_digest(destination) != old.get("sha256"):
            raise InstallError(f"modified managed file: {relative.as_posix()}")

    for relative in links:
        check_no_ancestor_symlinks(target, relative, allow_leaf=True)
        destination = target / relative
        if not destination.exists() and not destination.is_symlink():
            continue
        old = old_entries.get(relative.as_posix())
        if (
            old is None
            or old.get("type") != "symlink"
            or not destination.is_symlink()
            or os.readlink(destination) != old.get("target")
        ):
            raise InstallError(f"collision or modified symlink at {relative.as_posix()}")

    stale = {Path(path) for path in old_entries}.difference(desired_paths, SEED_PATHS)
    for relative in stale:
        check_no_ancestor_symlinks(target, relative, allow_leaf=True)
        destination = target / relative
        old = old_entries[relative.as_posix()]
        if old.get("type") == "file":
            if not destination.is_file() or destination.is_symlink():
                raise InstallError(f"modified managed path: {relative.as_posix()}")
            if file_digest(destination) != old.get("sha256"):
                raise InstallError(f"modified managed file: {relative.as_posix()}")
        elif old.get("type") == "symlink":
            if not destination.is_symlink() or os.readlink(destination) != old.get("target"):
                raise InstallError(f"modified managed symlink: {relative.as_posix()}")
        else:
            raise InstallError(f"invalid manifest entry: {relative.as_posix()}")
    return instruction_outputs, stale


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def git_output(target: Path, *arguments: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(target), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def prepare_git_exclude(
    target: Path,
    installed: set[Path],
    instruction_files: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md"),
) -> tuple[Path, bytes] | None:
    raw_path = git_output(target, "rev-parse", "--git-path", "info/exclude")
    if raw_path is None:
        print("warning: target is not a Git worktree; no local excludes written", file=sys.stderr)
        return None
    exclude = Path(raw_path)
    if not exclude.is_absolute():
        exclude = target / exclude
    if exclude.is_symlink():
        raise InstallError(f"unsafe Git exclude symlink: {exclude}")

    rules = {"/.harness/", "/.agents/skills/", "/.claude/skills/"}
    if any(path.parts[:2] == ("tools", "agents") for path in installed):
        rules.add("/tools/agents/")
    for relative in installed:
        if relative.parts and relative.parts[0] in {".harness", ".agents", ".claude", "tools"}:
            continue
        rules.add("/" + relative.as_posix())
    for instruction in instruction_files:
        if git_output(target, "ls-files", "--error-unmatch", "--", instruction) is None:
            rules.add("/" + instruction)

    block = EXCLUDE_BEGIN + "\n" + "\n".join(sorted(rules)) + "\n" + EXCLUDE_END
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if EXCLUDE_BEGIN in existing or EXCLUDE_END in existing:
        if existing.count(EXCLUDE_BEGIN) != 1 or existing.count(EXCLUDE_END) != 1:
            raise InstallError(f"malformed managed block in Git exclude: {exclude}")
        start = existing.index(EXCLUDE_BEGIN)
        finish = existing.index(EXCLUDE_END, start) + len(EXCLUDE_END)
        updated = existing[:start] + block + existing[finish:]
    else:
        separator = "" if not existing or existing.endswith("\n\n") else "\n"
        updated = existing + separator + block + "\n"
    return exclude, updated.encode()


def install(args: argparse.Namespace) -> None:
    harness_root = Path(__file__).resolve().parent
    raw_target = args.target.expanduser()
    if raw_target.is_symlink():
        raise InstallError(f"unsafe target directory symlink: {args.target}")
    target = raw_target.resolve()
    if not target.is_dir():
        raise InstallError(f"target does not exist or is not a directory: {args.target}")
    instruction_files = ("AGENTS.md", args.claude_instructions)
    if args.no_skills:
        # O projeto ja gerencia .agents/skills por conta propria (ex.: skills-lock.json);
        # instala so o payload do harness, sem vendoring nem symlinks de colecoes.
        sources: dict[str, Path] = {}
        collections: tuple[str, ...] = ()
    else:
        sources = discover_sources(args.skills_source)
        collections = COLLECTIONS
    regular, links = build_desired(harness_root, sources, collections)
    previous = read_manifest(target)
    instructions = (harness_root / "files/AGENTS.md").read_text(encoding="utf-8")
    block = managed_text(instructions)
    instruction_outputs, stale = preflight(
        target, regular, links, previous, block, instruction_files
    )
    installed_paths = set(regular) | set(links) | {MANIFEST_PATH}
    git_exclude = prepare_git_exclude(target, installed_paths, instruction_files)

    if args.dry_run:
        print(
            f"dry-run: validated {len(regular)} files, {len(links)} skill links, "
            "and 2 instruction files; nothing written"
        )
        return

    for relative in sorted(stale, key=lambda p: len(p.parts), reverse=True):
        destination = target / relative
        if destination.is_symlink() or destination.exists():
            destination.unlink()
    for relative, (data, mode, _source) in sorted(regular.items(), key=lambda item: str(item[0])):
        if relative in SEED_PATHS and (target / relative).exists():
            continue
        atomic_write(target / relative, data, mode)
    for relative, link_target in sorted(links.items(), key=lambda item: str(item[0])):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            destination.unlink()
        destination.symlink_to(link_target, target_is_directory=True)
    for name, content in instruction_outputs.items():
        destination = target / name
        if not destination.exists() or destination.read_text(encoding="utf-8") != content:
            atomic_write(destination, content.encode(), 0o644)

    entries: dict[str, dict[str, str]] = {}
    for relative, (data, _mode, provenance) in regular.items():
        if relative in SEED_PATHS:
            continue
        entries[relative.as_posix()] = {
            "type": "file",
            "sha256": digest(data),
            "provenance": provenance,
        }
    for relative, link_target in links.items():
        entries[relative.as_posix()] = {"type": "symlink", "target": link_target}
    manifest = {
        "version": 1,
        "managed_block_hash": digest(block.encode()),
        "skill_sources": {name: str(sources[name]) for name in collections},
        "entries": dict(sorted(entries.items())),
    }
    atomic_write(
        target / MANIFEST_PATH,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
    )
    if git_exclude is not None:
        exclude_path, exclude_content = git_exclude
        atomic_write(exclude_path, exclude_content, 0o644)
    print(f"installed {len(regular)} files and {len(links)} skill links in {target}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the portable agent harness from local sources only."
    )
    parser.add_argument("target", type=Path)
    parser.add_argument(
        "--skills-source",
        action="append",
        default=[],
        type=Path,
        metavar="PATH",
        help="checkout root or skills directory (repeat for both collections)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-skills",
        action="store_true",
        help="skip vendoring upstream skill collections (project manages .agents/skills itself)",
    )
    parser.add_argument(
        "--claude-instructions",
        default="CLAUDE.md",
        choices=("CLAUDE.md", "CLAUDE.local.md"),
        help="which Claude instruction file receives the managed block (default: CLAUDE.md)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        install(parse_args(sys.argv[1:] if argv is None else argv))
    except InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
