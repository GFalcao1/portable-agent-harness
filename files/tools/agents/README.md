# Local multi agent setup

This layer only serves the twelve spawned roles of this project plus the
orchestrator. The orchestrator is the main Claude Code session and it is
the one holding decisions and task state. The `multi-agent` skill prepares
self contained handoffs and this wrapper calls the Claude Code CLI, the
Codex CLI (for planner, code reviewer and security reviewer) and AGY,
whenever it is installed. There is no server and no daemon running
anywhere.

## The fixed roster

`agents.json` in this directory is the single source of truth for every
role's model, effort, provider and status — do not duplicate those values
here, they drift. The roster currently has thirteen entries: `orchestrator`
plus the twelve spawned roles (`task-manager`, `planner`,
`researcher-primary`, `researcher-deep`, `codebase-explorer`,
`implementer`, `implementation-worker`, `deep-debugger`, `code-reviewer`,
`security-reviewer`, `verifier`, `docs-mechanical`). READY only means
declared and covered by a test, it says nothing about authentication,
quota or future availability.

`planner`, `code-reviewer` and `security-reviewer` are intentionally routed
to the Codex CLI, kept consistent with the task contracts under `task/`;
see `docs/agent-workflow.md` for the design rationale.

## Account budget for the Codex-based roles

The Codex-based roles (planner, code reviewer, security reviewer) only
spend whatever limit the linked ChatGPT/Codex account already has;
`agents.json` does not need a dedicated field for this since the
enforcement lives in the wrapper and in the harness instructions, not in
the roster file. The guarantee sits on three layers.

1. Account side. Whatever plan or limit the linked Codex account has,
   outside this harness entirely. The wrapper has no way to touch that, by
   construction.
2. Wrapper side. Any limit error ("usage limit", "you've hit your usage
   limit", HTTP 429) comes back as BLOCKED, never FAIL, never PASS, and the
   wrapper does not retry on its own. The markers live in `QUOTA_MARKERS`
   inside `delegate.py`.
3. Instruction side. `AGENTS.md` and the `multi-agent` skill forbid the
   orchestrator from upgrading the plan, buying credits, or swapping a
   Codex-based role for a different model when it gets blocked.

Budget per task lives in `.agents/skills/multi-agent/references/orcamento-e-lanes.md`.

## Skills per role

The wrapper runs Claude roles with `--restricted --strict-mcp-config` and,
for every single invocation, builds a throwaway plugin that only symlinks
the skills that specific role is allowed to see. Codex roles (planner, code
reviewer, security reviewer) get the same skill text prepended to the
prompt instead, since Codex has no `--plugin-dir` mechanism. Resolution
checks `.agents/skills/<name>` inside this project first (managed by
`skills-lock.json`), and only falls back to the plugin cache after that.

* task manager, researcher deep, codebase explorer, verifier and docs
  mechanical all get `caveman/caveman` (resolves to `.claude/skills/caveman`)
* planner gets `caveman/caveman` plus `superpowers/writing-plans`
* implementer gets `caveman/caveman`, plus
  `mattpocock-skills/engineering/tdd` (resolves to `.agents/skills/tdd`),
  plus `superpowers/executing-plans` (from the `superpowers` plugin cache)
* deep debugger gets `caveman/caveman` plus
  `superpowers/systematic-debugging`; confirm this skill actually resolves
  on the current machine before treating the role as READY there
* code reviewer and security reviewer both get `caveman/caveman` plus
  `mattpocock-skills/engineering/code-review`
* researcher primary and implementation worker get nothing at all, they run
  through AGY with `--disable-slash-commands`

Every role runs caveman for terse output and lower token spend without
losing technical precision. It got installed with
`npx skills add JuliusBrussee/caveman -a claude-code` (both globally and
inside the project), keeping only `caveman`, `caveman-commit`,
`caveman-compress`, `caveman-help`, `caveman-review` and `caveman-stats`.
The `superpowers` plugin got installed at user scope through
`claude plugin install superpowers@claude-plugins-official`.

A skill that gets declared but is not actually present returns BLOCKED. AGY
always keeps `--disable-slash-commands` on.

## Running it

Open Claude Code at the root of the checkout as the orchestrator, then
delegate from there.

```sh
python3 tools/agents/delegate.py --agent codebase-explorer --prompt-file /tmp/tarefa.txt
python3 tools/agents/delegate.py --agent researcher-primary < /tmp/pesquisa.txt
python3 tools/agents/delegate.py --agent planner < /tmp/tarefa.txt          # CRITICAL only
python3 tools/agents/delegate.py --agent implementer < /tmp/plano-aprovado.txt
python3 tools/agents/delegate.py --agent code-reviewer < /tmp/diff-e-plano.txt
python3 tools/agents/delegate.py --agent security-reviewer < /tmp/diff-e-plano.txt   # quando aplicável
python3 tools/agents/delegate.py --agent verifier --test-suite audit < /tmp/verificacao.txt
```

The suites the verifier is allowed to run live in `project.json`, right now
that is `agents`, `audit`, `parametrizacao`, `unit` and `lint`. All of them
run from the repo root through `.venv/bin/python -m pytest ...` or
`.venv/bin/ruff check .`. Commands are literal strings, no shell operators,
no wildcards, add a new suite to that JSON file instead of ever handing out
unrestricted shell access.

The JSON response back carries agent, provider, model, reasoning_effort,
status, response and exit_code. A PASS in that envelope just means the call
executed cleanly, always go read the actual VERDICT the specialist wrote in
its response. A timeout comes back as BLOCKED with exit code 124, a missing
CLI comes back as BLOCKED with exit code 127, and a permission denial, a
spent budget or a missing skill all come back as BLOCKED too. A role that
answers under a different identity than what was requested comes back as
FAIL.

## Permissions and concurrency

Task manager, planner, researcher primary, researcher deep, codebase
explorer, deep debugger, code reviewer and security reviewer are all read
only, no shell access at all. Implementer, implementation worker and docs
mechanical can read and edit (or, for the AGY role, edit through
`--mode accept-edits`) but still get no shell. Verifier gets read access plus
exactly the one test command tied to whatever suite you picked. Passing
`--smoke` strips out every tool and every skill. Nothing starting with
`CLAUDE_CODE_` ever leaks through to Codex or AGY. One flock per repo root
keeps implementer, implementation worker and docs mechanical from ever
running at the same time.

Same working tree plus multiple writers is prohibited, full stop.

## Tests

```sh
.venv/bin/python -m pytest tests/test_agent_delegation.py -q
.venv/bin/ruff check tools/agents/delegate.py tests/test_agent_delegation.py
python3 tools/agents/delegate.py --agent orchestrator --smoke < /dev/null   # should come back BLOCKED
```

A real smoke test per role spends real provider budget/quota — run each one
once, never in a loop. Every role's prompt just asks it to identify itself
and echo a fixed token (for example, "Act as the code reviewer. Return
exactly: CODE_REVIEWER_OK"); a role that can edit files gets told not to.
Keep the last smoke-test run's date and outcome per role in your own notes
or task log rather than baking it into this file, since it goes stale the
moment the roster or the machine changes.

## Troubleshooting and known limits

* Recheck `claude --help`, `codex exec --help` and `agy --help` after
  upgrading any CLI, the wrapper depends on very specific flags that could
  change.
* A spent limit is always BLOCKED, it is never a reason to swap the model
  or to enable extra usage.
* The Claude CLI retries on its own when it hits a 429 before giving up
  (you will see `api_retry` events), that does not buy any credit, it just
  waits. The wrapper still classifies the final result as BLOCKED.
* Where `agy` is installed, do not fan out several AGY calls at once — a
  transient failure has been observed under concurrent load, with a PASS
  on a single sequential retry. `agy` also prints `warning: --mode plan
  has no effect while slash command expansion is disabled`, meaning the
  read-only guarantee for researcher primary rests on `--sandbox` alone,
  not on `--mode plan`. If `agy` is missing on a given machine, both AGY
  roles come back BLOCKED with exit code 127 and the only sanctioned
  fallback is the implementer role, never a silent model swap.
* The lock only coordinates calls that go through this wrapper, it does
  nothing for editors or CLIs invoked directly.
* POSIX only.
