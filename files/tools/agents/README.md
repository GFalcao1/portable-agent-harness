# Local multi agent setup, Project Hermes

This layer only serves the seven roles of this project. The orchestrator is
the main Claude Code session and it is the one holding decisions and task
state. The `multi-agent` skill prepares self contained handoffs and this
wrapper calls the Claude Code CLI (and AGY, whenever it is installed). There
is no server and no daemon running anywhere. Codex is not part of this
project's roster, the adapter stays in the code and in the tests only so it
does not turn into dead code.

## The fixed roster

* orchestrator, requested Sonnet 5, resolves to `claude-sonnet-5`, runs as
  the parent Claude Code session, effort high, status READY
* researcher, requested Opus 5, resolves to `claude-opus-5`, Claude Code
  CLI, effort low, status READY
* planner, requested Fable 5.1, resolves to `claude-fable-5-1`, Claude Code
  CLI, effort medium, status READY
* implementer, requested Sonnet 5, resolves to `claude-sonnet-5`, Claude
  Code CLI, effort medium, status READY
* implementer bulk, requested Gemini Pro 3.1, resolves to
  `gemini-3.1-pro-high`, provider AGY, native effort, READY in the roster
  but `agy` is missing on this machine so it comes back BLOCKED with exit
  code 127
* code reviewer, requested Fable 5.1, resolves to `claude-fable-5-1`,
  Claude Code CLI, effort high, status READY
* verifier, requested Opus 5, resolves to `claude-opus-5`, Claude Code CLI,
  effort high, status READY

The single source of truth for all of this is `agents.json`. READY only
means declared and covered by a test, it says nothing about authentication,
quota or future availability.

Fable 5.1's identity was proven for real on 2026 09 18. A live smoke run of
`--agent code-reviewer --smoke` came back PASS with `reported_model:
claude-fable-5-1`, one turn, about 5.6 seconds, 57 output tokens (42 of them
thinking), `service_tier: standard`. The planner uses that exact same model
and only differs in effort.

## Fable 5.1 budget

Fable roles carry `"budget": "admin-limit-only"` in `agents.json`. Claude
Code has no flag, no env var and no settings key to control buying extra
usage, that lives entirely in the org admin panel (Admin Settings, Usage)
and, on the CLI side, only through the interactive `/usage-credits` command,
which does not even exist in `--print` mode. The guarantee sits on three
layers.

1. Admin side. Extra credit disabled or a monthly cap set outside this
   harness entirely. The wrapper has no way to touch that, by construction.
2. Wrapper side. Any limit error (HTTP 429, a `system/api_retry` event with
   `error_status` 429, or a message containing something like "usage
   limit", "spend limit", "rate limit", "extra usage", "quota") comes back
   as BLOCKED, never FAIL, never PASS, and the wrapper does not retry on its
   own. The markers live in `QUOTA_MARKERS` inside `delegate.py`.
3. Instruction side. `AGENTS.md`, `CLAUDE.local.md` and the skill itself all
   forbid the orchestrator from calling `/usage-credits`, asking for a
   higher limit, or swapping Fable for a different model when it gets
   blocked.

Budget per task, two Fable calls on CRITICAL work (planner plus code
reviewer), one call on everything else (code reviewer only).

## What we found on this machine (2026 09 18)

Linux x86_64, bash. Claude Code 2.1.276, Codex 0.154.0 (not used), `agy` is
missing, `uv` is missing too so `.venv/bin/python` is what gets used
instead. Running `claude --help` confirmed every flag the wrapper relies on
`--print`, `--model`, `--effort`, `--output-format stream-json`,
`--verbose`, `--no-session-persistence`, `--restricted`,
`--strict-mcp-config`, `--permission-prompts none`, `--permission-mode`,
`--tools`, `--allowedTools`, `--plugin-dir`. Plugin cache only has
`mattpocock-skills` (1.2.3), `superpowers` is not installed, which is why
the installer runs with `--no-skills` on this project.

## Skills per role

The wrapper runs with `--restricted --strict-mcp-config` and, for every
single invocation, builds a throwaway plugin that only symlinks the skills
that specific role is allowed to see. Resolution checks
`.agents/skills/<name>` inside this project first (managed by
`skills-lock.json`), and only falls back to the plugin cache after that.

* researcher, planner, code reviewer and verifier all get `caveman/caveman`
  (resolves to `.claude/skills/caveman`)
* implementer gets `caveman/caveman`, plus
  `mattpocock-skills/engineering/tdd` (resolves to `.agents/skills/tdd`),
  plus `superpowers/executing-plans` (from the `superpowers` plugin cache)
* implementer bulk gets nothing at all, it runs through AGY with
  `--disable-slash-commands`

Every Claude role runs caveman for terse output and lower token spend
without losing technical precision. It got installed on 2026 09 18 with
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
python3 tools/agents/delegate.py --agent researcher --prompt-file /tmp/tarefa.txt
python3 tools/agents/delegate.py --agent planner < /tmp/tarefa.txt          # CRITICAL only
python3 tools/agents/delegate.py --agent implementer < /tmp/plano-aprovado.txt
python3 tools/agents/delegate.py --agent code-reviewer < /tmp/diff-e-plano.txt
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
responding as if it were Fable) comes back as FAIL.

## Permissions and concurrency

Researcher, planner and code reviewer are all read only, no shell access at
all. Implementer can read and edit but still gets no shell. Verifier gets
read access plus exactly the one test command tied to whatever suite you
picked. Passing `--smoke` strips out every tool and every skill. Nothing
starting with `CLAUDE_CODE_` ever leaks through to AGY. One flock per repo
root keeps implementer and implementer bulk from ever running at the same
time.

Same working tree plus multiple writers is prohibited, full stop.

## Tests

```sh
.venv/bin/python -m pytest tests/test_agent_delegation.py -q
.venv/bin/ruff check tools/agents/delegate.py tests/test_agent_delegation.py
python3 tools/agents/delegate.py --agent orchestrator --smoke < /dev/null   # should come back BLOCKED
```

A real smoke test per role (this spends real provider budget, and the
Fable ones eat directly into the admin defined limit, run each one once,
never in a loop)

* researcher, prompt "Act as the researcher. Return exactly: RESEARCHER_OK"
* planner, prompt "Act as the planner. Return exactly: PLANNER_OK"
* implementer, prompt "Identify yourself as the implementation agent. Do
  not modify files. Return exactly: IMPLEMENTER_OK"
* code reviewer, prompt "Act as the code reviewer. Return exactly:
  CODE_REVIEWER_OK"
* verifier, prompt "Act as the verifier. Return exactly: VERIFIER_OK"

## Troubleshooting and known limits

* Recheck `claude --help` after upgrading the CLI, the wrapper depends on
  very specific flags that could change.
* A spent limit is always BLOCKED, it is never a reason to swap the model
  or to enable extra usage.
* The CLI retries on its own when it hits a 429 before giving up (you will
  see `api_retry` events), that does not buy any credit, it just waits.
  The wrapper still classifies the final result as BLOCKED.
* Lane B (Gemini through AGY) stays BLOCKED until the `agy` CLI is actually
  installed and validated on the machine.
* The lock only coordinates calls that go through this wrapper, it does
  nothing for editors or CLIs invoked directly.
* POSIX only.
