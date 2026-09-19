# Portable Agent Harness

## What this thing actually is

This repo is not a workflow by itself. It is an installer for a workflow.

The installer (`install.py`, wrapped by `install.sh`) copies a fixed set of
files into some other project on your machine. Those copied files are the
real thing: a multi agent delegation setup for Claude Code and friends, built
around a locked roster of roles (orchestrator, researcher, planner,
implementer, implementer bulk, code reviewer, verifier), each one pinned to a
specific model, effort level, provider CLI and set of tools. A python wrapper
called `tools/agents/delegate.py` is the piece that actually spawns those
roles as subprocesses, parses their output, enforces a write lock so two
writer roles never touch the same tree at once, and reports back a clean
PASS FAIL BLOCKED verdict instead of letting anything fail silently.

So think of it as two layers. This harness is the packaging and delivery
mechanism. What it delivers, once installed, is the actual multi agent
orchestration system that runs inside your target project.

It is config you own personally, not something you check into a project git
history. The installer takes care of that on its own by writing a local rule
into `.git/info/exclude` on the target repo, which never gets committed.

## What gets installed into a project

Once you run the installer against a target repo, you end up with

* `AGENTS.md`, the rules the orchestrator session itself follows, including
  lane routing and the parent session budget
* `.agents/skills/multi-agent/SKILL.md`, how to pick a role, delegate to it
  and read what it hands back
* `tools/agents/agents.json`, the fixed roster: model, effort, provider and
  mode per role
* `tools/agents/delegate.py`, the wrapper that spawns each role with a locked
  down argv
* `tools/agents/README.md`, operation notes, permissions, concurrency and
  known limits
* `tests/test_agent_delegation.py`, roughly fifty tests covering the wrapper
  behavior
* `docs/agent-workflow.md`, the design writeup and why it looks like this
* `task/COMPLEXIDADE.md`, the complexity gate that decides which lane a task
  runs on
* `tools/agents/project.json`, the literal test suites the verifier role is
  allowed to run

The installer refuses to run if any of these already exist at the target, it
never overwrites anything on its own.

## Setting this up on a new machine, step by step

### 1. Put the harness somewhere permanent

This copy lives at

```
~/.local/share/portable-agent-harness
```

That is the XDG style spot for tool data that is not itself an app bundle,
matching what already sits next to it on this machine (`claude`, `uv`). If
you are setting this up fresh on another machine, clone or copy this whole
folder there.

### 2. Expose a global command

Drop a small wrapper script at `~/.local/bin/agent-harness` (already on PATH
on this machine) that forwards to the real scripts

```sh
#!/usr/bin/env bash
set -euo pipefail
HARNESS_HOME="$HOME/.local/share/portable-agent-harness"
case "${1:-}" in
  fetch-skills)
    shift
    exec "$HARNESS_HOME/fetch-skills.sh" "$@"
    ;;
  *)
    exec python3 "$HARNESS_HOME/install.py" "$@"
    ;;
esac
```

Make it executable with `chmod +x ~/.local/bin/agent-harness`. From this
point on you can type `agent-harness` from inside any project directory,
anywhere on the machine, no need to `cd` into the harness folder first.

### 3. Pull the skill collections

The roles reference skills that live in shared plugin collections
(`caveman`, `superpowers`, `mattpocock-skills`). Grab them once per machine

```sh
agent-harness fetch-skills
```

This is a separate, explicit step on purpose. The installer itself never
reaches out to the network, it only copies from sources you already trust
locally (a plugin cache or an explicit `--skills-source`).

### 4. Install into an actual project

```sh
cd /path/to/your/project
agent-harness .
```

or pass the path directly from anywhere

```sh
agent-harness /path/to/your/project
```

Common flags

* `--no-skills`, skip vendoring the skill collections if your project
  already manages `.agents/skills` on its own (say, via a `skills-lock.json`)
* `--claude-instructions CLAUDE.local.md`, write the managed instructions
  block into a local, untracked file instead of touching the project's
  versioned `CLAUDE.md`
* `--dry-run`, see what would happen without touching anything
* `--skills-source PATH`, point at a specific checkout instead of the plugin
  cache

This step is per project. Having the global command available does not make
the workflow active everywhere automatically, it just means you do not have
to remember where the source lives to run the installer.

### 5. Sanity check the install

```sh
python3 tools/agents/delegate.py --agent orchestrator --smoke < /dev/null
.venv/bin/python -m pytest tests/test_agent_delegation.py -q
```

The first call should come back BLOCKED with a note pointing you at opening
the parent session yourself, since the wrapper never starts the orchestrator
on its own. The test suite is hermetic, it resolves skills against a fake
cache so it passes even on a machine without the real plugins installed.

To prove the real providers actually work, smoke test a role or two for real

```sh
echo "Return exactly: OK" | python3 tools/agents/delegate.py --agent researcher --smoke
echo "Return exactly: OK" | python3 tools/agents/delegate.py --agent code-reviewer --smoke
```

## The reference role roster

This is the matrix shipped by default, from the project it was pulled out
of. Treat it as the example to adapt, not a fixed law of nature.

* orchestrator, claude sonnet 5, high effort, the parent Claude Code session
  itself, mode write
* researcher, claude opus 5, low effort, Claude Code CLI, mode read only
* planner, claude fable 5.1, medium effort, Claude Code CLI, mode read only
* implementer, claude sonnet 5, medium effort, Claude Code CLI, mode write
* implementer bulk, gemini 3.1 pro high, native effort, AGY, mode write, only
  inside an isolated worktree
* code reviewer, claude fable 5.1, high effort, Claude Code CLI, mode read
  only
* verifier, claude opus 5, high effort, Claude Code CLI, mode read and
  execute

The orchestrator is the session you open by hand, never a subprocess. Every
other role gets spawned by the wrapper with its model and effort locked into
the argv. There is no silent swap if a model is missing or its budget is
spent, that returns BLOCKED instead.

Fable roles only spend whatever budget an admin already configured for them.
The wrapper never asks for or enables extra usage on your behalf, and once a
Fable role hits its limit the whole task just sits BLOCKED until that limit
resets. More detail on that in `files/tools/agents/README.md`.

## The two lanes

Lane A covers anything tagged IMPORTANT or CRITICAL. Sonnet implements,
Fable reviews, at most one repair round happens, then the verifier closes it
out.

Lane B is only for TRIVIAL and SMALL work. Tests get committed in a failing
RED state first, Gemini implements inside an isolated worktree, then Sonnet
runs those tests, checks the result against the plan and closes any gap. No
Fable review here, Sonnet already acts as an independent reviewer since it
did not write the code.

Gemini never owns anything touching security, migrations, concurrency,
recovery, credentials or destructive data operations, full stop.

## Adjusting this for your own project

Four knobs, all called out directly in code or docs

1. `tools/agents/project.json`, one entry per test suite the verifier is
   allowed to run. This replaces `CANONICAL_TEST_COMMANDS` at runtime. The
   command is literal, no agent gets to modify it.
2. `task/COMPLEXIDADE.md`, classify your own units of work here. Without
   this the two lanes have no real gate and just become a matter of opinion.
3. `ROLE_SKILLS` inside `delegate.py`, which skills each role gets handed.
   Paths point at plugins installed under
   `~/.claude/plugins/cache/claude-plugins-official`. A skill that is
   declared but missing returns BLOCKED on purpose, it does not fall back to
   nothing.
4. `ROLE_OUTPUT_CEILING`, a line count cap on how long each role's final
   report is allowed to be.

## What you need before any of this works

An authenticated `claude` CLI (Codex is not wired into this particular
project, `agy` is optional and only needed for lane B), plus whatever skills
each role declares in `ROLE_SKILLS` inside `delegate.py`. The versions this
was actually validated against are listed in `tools/agents/README.md`.
Recheck help output and catalogs after upgrading any CLI, this harness
depends on very specific flags (`--plugin-dir`, `--restricted`,
`--no-session-persistence`, `agy --mode accept-edits`).

## Known rough edges

* Fable 5.1's identity gets checked against the actual event stream. The
  wrapper marks the run FAIL if the model reported in the `assistant` or
  `init` events does not match `claude-fable-5-1`.
* There is no programmatic control over extra usage inside Claude Code
  itself. The guarantee of only spending an admin defined limit depends on
  that admin side configuration plus the wrapper's BLOCKED behavior and the
  instructions handed to the orchestrator.
* Lane B has never actually run for real, and `agy` is not installed on this
  machine right now.
* Nothing verifies the orchestrator's own effort level.
* POSIX only. The wrapper just returns BLOCKED on Windows.
* The write lock only coordinates calls that go through this wrapper. It has
  no effect on editors or CLIs invoked directly outside of it.
