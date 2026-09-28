# Local multi agent setup

This layer only serves the twelve roles of this project. The orchestrator is
the main Claude Code session and it is the one holding decisions and task
state. The `multi-agent` skill prepares self contained handoffs and this
wrapper calls the Claude Code CLI, the Codex CLI (for planner, code
reviewer and security reviewer) and AGY, whenever it is installed. There is
no server and no daemon running anywhere.

## The fixed roster

* orchestrator, requested Sonnet 5, resolves to `claude-sonnet-5`, runs as
  the parent Claude Code session, effort high, status READY
* task manager, requested Opus 5.5, resolves to `claude-opus-5-5`, Claude
  Code CLI, effort high, status READY
* planner, requested Astra, resolves to `gpt-6-astra`, Codex CLI, effort
  medium, status READY
* researcher primary, requested Gemini 3.8 Flash, resolves to
  `gemini-3.8-flash-high`, provider AGY, native effort baked into the model
  id suffix, status READY, smoke test passed on September 28 2026 (`agy`
  1.2.7; one transient FAIL under 7 parallel calls, PASS on a single retry)
* researcher deep, requested Fable 5.1, resolves to `claude-fable-5-1`,
  Claude Code CLI, effort medium, status READY
* codebase explorer, requested Sonnet 5, resolves to `claude-sonnet-5`,
  Claude Code CLI, effort medium, status READY
* implementer, requested Sonnet 5, resolves to `claude-sonnet-5`, Claude
  Code CLI, effort medium, status READY
* implementation worker, requested Gemini 3.8 Flash, resolves to
  `gemini-3.8-flash-medium`, provider AGY, native effort, status READY, smoke
  test passed on September 28 2026
* deep debugger, requested Opus 5.5, resolves to `claude-opus-5-5`, Claude
  Code CLI, effort high, status READY
* code reviewer, requested Astra, resolves to `gpt-6-astra`, Codex CLI,
  effort medium, status READY
* security reviewer, requested Astra, resolves to `gpt-6-astra`, Codex CLI,
  effort medium, status READY
* verifier, requested Sonnet 5, resolves to `claude-sonnet-5`, Claude Code
  CLI, effort medium, status READY
* docs mechanical, requested Sonnet 5, resolves to `claude-sonnet-5`, Claude
  Code CLI, effort low, status READY

The single source of truth for all of this is `agents.json`. READY only
means declared and covered by a test, it says nothing about authentication,
quota or future availability.

Astra owns the planner, code reviewer and security reviewer roles because it
wrote the 65 task files under `task/` in the first place (see
`docs/agent-workflow.md`); keeping it on critical planning and review keeps
things consistent with the contracts it defined itself.

## Astra account budget

Astra roles (planner, code reviewer, security reviewer) only spend whatever
limit the linked ChatGPT/Codex account already has; `agents.json` does not
need a dedicated field for this since the enforcement lives in the wrapper
and in these instructions, not in the roster file. The guarantee sits on
three layers.

1. Account side. Whatever plan or limit the linked Codex account has,
   outside this harness entirely. The wrapper has no way to touch that, by
   construction.
2. Wrapper side. Any limit error ("usage limit", "you've hit your usage
   limit", HTTP 429) comes back as BLOCKED, never FAIL, never PASS, and the
   wrapper does not retry on its own. The markers live in `QUOTA_MARKERS`
   inside `delegate.py`.
3. Instruction side. `AGENTS.md`, `CLAUDE.local.md` and the skill itself all
   forbid the orchestrator from upgrading the plan, buying credits, or
   swapping Astra for a different model when it gets blocked.

Budget per task: on CRITICAL work, at most one planner call plus one code
reviewer call, plus one extra security reviewer call only when the change is
materially security-relevant (auth, authz, credentials, secrets, PII,
upload, untrusted parsing, external execution, network, SQL, permissions,
destructive ops). On IMPORTANT work, one code reviewer call. On SMALL and
TRIVIAL, zero Astra calls.

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
  `superpowers/systematic-debugging`; on this machine that skill resolves at
  `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.4.1/skills/systematic-debugging`,
  so the role is fully READY here — re-check on any other machine before
  assuming the same
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

Open Claude Code at the root of the checkout on `claude-sonnet-5` with high
effort, then delegate from there.

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
spent budget or a missing skill all come back as BLOCKED too. A model that
answers under a different identity than what was requested (say Opus
responding as if it were Astra) comes back as FAIL.

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

A real smoke test per role (this spends real provider budget/quota, run
each one once, never in a loop)

Results on September 28 2026: task manager, researcher deep, codebase
explorer, deep debugger, security reviewer, verifier, implementation worker
and docs mechanical all PASS with the requested model reported back (Codex
and AGY do not report a model id, so `reported_model` is null there);
researcher primary PASS on retry, see Troubleshooting.

* task manager, prompt "Act as the task manager. Return exactly: TASK_MANAGER_OK"
* planner, prompt "Act as the planner. Return exactly: PLANNER_OK"
* researcher primary, prompt "Act as the researcher. Return exactly:
  RESEARCHER_OK" — PASS on September 28 2026
* researcher deep, prompt "Act as the researcher. Return exactly:
  RESEARCHER_OK"
* codebase explorer, prompt "Act as the codebase explorer. Return exactly:
  EXPLORER_OK"
* implementer, prompt "Identify yourself as the implementation agent. Do
  not modify files. Return exactly: IMPLEMENTER_OK"
* implementation worker, prompt "Identify yourself as the implementation
  agent. Do not modify files. Return exactly: IMPLEMENTER_OK" — PASS on
  September 28 2026
* deep debugger, prompt "Act as the deep debugger. Return exactly:
  DEBUGGER_OK"
* code reviewer, prompt "Act as the code reviewer. Return exactly:
  CODE_REVIEWER_OK"
* security reviewer, prompt "Act as the security reviewer. Return exactly:
  SECURITY_REVIEWER_OK"
* verifier, prompt "Act as the verifier. Return exactly: VERIFIER_OK"
* docs mechanical, prompt "Act as the docs/mechanical agent. Do not modify
  files. Return exactly: DOCS_OK"

## Troubleshooting and known limits

* Recheck `claude --help`, `codex exec --help` and `agy --help` after
  upgrading any CLI, the wrapper depends on very specific flags that could
  change.
* A spent limit is always BLOCKED, it is never a reason to swap the model
  or to enable extra usage.
* The Claude CLI retries on its own when it hits a 429 before giving up
  (you will see `api_retry` events), that does not buy any credit, it just
  waits. The wrapper still classifies the final result as BLOCKED.
* `agy` is installed on this machine (1.2.7, `~/.local/bin/agy`) and both
  AGY roles passed their smoke test on September 28 2026, so Lane B is
  validated here. Two caveats from that run: (1) the researcher primary
  smoke came back FAIL once ("provider returned no usable response") while
  seven roles ran in parallel and passed on a single sequential retry, so
  do not fan out several AGY calls at once; (2) `agy` prints
  `warning: --mode plan has no effect while slash command expansion is
  disabled`, meaning the read-only guarantee for researcher primary rests
  on `--sandbox` alone, not on `--mode plan`. If `agy` turns out to be
  missing on some other machine, both roles come back BLOCKED with exit code
  127 and the only sanctioned fallback is the implementer (Sonnet), never a
  silent model swap.
* The lock only coordinates calls that go through this wrapper, it does
  nothing for editors or CLIs invoked directly.
* POSIX only.
