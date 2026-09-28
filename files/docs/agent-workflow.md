# Agent workflow orchestrated by Sonnet

> Project Hermes amendment, September 28 2026. The role matrix moved from
> seven roles to the thirteen-entry matrix (orchestrator plus twelve spawned
> roles) defined in `CLAUDE.local.md` section 2 and mirrored in
> `agents.json`. The "Role matrix" section below, and every reference to
> `researcher` or `implementer-bulk` as role names, is **superseded**.
>
> New roster: `orchestrator` (unchanged), `task-manager` (Opus 5.5, high,
> Claude Code CLI, replaces nothing, new role), `planner` (Astra, medium,
> Codex CLI, unchanged), `researcher-primary` (Gemini 3.8 Flash, native
> effort, AGY, `--mode plan`, replaces `researcher`), `researcher-deep`
> (Fable 5.1, medium, Claude Code CLI, new role, called only when research
> is contentious or CRITICAL), `codebase-explorer` (Sonnet 5, medium, Claude
> Code CLI, new role), `implementer` (Sonnet 5, medium, Claude Code CLI,
> unchanged), `implementation-worker` (Gemini 3.8 Flash, native effort, AGY,
> `--mode accept-edits`, replaces `implementer-bulk`), `deep-debugger` (Opus
> 5.5, high, Claude Code CLI, new role), `code-reviewer` (Astra, **medium**,
> down from high, Codex CLI), `security-reviewer` (Astra, medium, Codex CLI,
> new role, same mechanics as `code-reviewer`), `verifier` (**Sonnet 5**,
> **medium**, down from Opus 5.5 high, Claude Code CLI) and
> `docs-mechanical` (Sonnet 5, low, Claude Code CLI, new role).
>
> Astra budget changed to match the new roles: CRITICAL work spends at most
> one planner call plus one code reviewer call, plus one extra security
> reviewer call only when the change is materially security-relevant (auth,
> authz, credentials, secrets, PII, upload, untrusted parsing, external
> execution, network, SQL, permissions, destructive ops); IMPORTANT spends
> at most one code reviewer call; SMALL and TRIVIAL spend zero.
>
> `agy` (1.2.7) is now installed at `~/.local/bin/agy` on this machine,
> unlike the September 11 write-up below which still treated it as entirely
> hypothetical. Both AGY roles (`researcher-primary`,
> `implementation-worker`) passed a real smoke test on September 28 2026,
> so Lane B is validated on this machine; the implementer (Sonnet)
> remains the only sanctioned fallback, never a silent model swap. Note
> that `agy` ignores `--mode plan` while `--disable-slash-commands` is on,
> so the read-only guarantee for `researcher-primary` comes from
> `--sandbox`. Current
> source of truth for skills, tools and output ceilings per role:
> `tools/agents/README.md` and `tools/agents/delegate.py`
> (`ROLE_SKILLS`/`ROLE_TOOLS`/`ROLE_OUTPUT_CEILING`).
>
> The "Write isolation" section below still describes two spawned writer
> roles sharing the lock; there are three now (`implementer`,
> `implementation-worker`, `docs-mechanical`), enforced by `WRITER_ROLES` in
> `delegate.py`. That section, like "Role matrix", is superseded.
>
> Project Hermes amendment, September 19 2026. The September 18 amendment
> below moved planner and code reviewer onto Claude Fable 5.1; that move was
> reverted the next day back onto `gpt-6-astra` through `codex exec`, at the
> exact same effort levels (medium and high). `agents.json` and this
> project's `AGENTS.md` are the live source of truth and both say Astra.
> Kept the September 18 text as history right below, since it is a real
> record of what was tried; read "Fable 5.1" in it as superseded.
>
> Project Hermes amendment, September 18 2026 (superseded, see above). The
> planner and code reviewer roles, originally running on `gpt-6-astra`
> through `codex exec`, moved onto Claude Fable 5.1 (`claude-fable-5-1`)
> through the Claude Code CLI, at the exact same effort levels (medium and
> high). One extra rule on top of that, Fable only spends whatever limit or
> budget the org admin already configured, a spent limit is BLOCKED, and
> nothing in this system ever asks for or enables extra usage.
> Everything below keeps the original design writeup intact, wherever it
> still says "Astra" that is, again, the live configuration for this
> project.

Date, September 11 2026.
Scope, the role matrix, provider routing, the Gemini and Sonnet split, the
repair loop, keeping token spend low, and skills per role.
Replaces, the routing proposed in
`2026-09-10-complexity-aware-agent-routing-design.md` for the role part
(`planner-light`, `code-generator`), and the fixed matrix that used to live
in `AGENTS.md`. The complexity classification in `task/COMPLEXIDADE.md`
stays valid and turns into a real routing gate.

## Goal

Move orchestration off Codex and onto Sonnet 5, keep Gemini restricted to
low complexity bulk work, cut the cost of every handoff, and give each role
exactly the skills it actually uses, all without loosening write isolation
or ever allowing a silent model swap.

## Role matrix

* orchestrator, `claude-sonnet-5`, effort high, runs as the parent Claude
  Code session, mode write
* researcher, `claude-opus-5`, effort low, Claude Code CLI, mode read only
* planner, `gpt-6-astra`, effort medium, Codex CLI, mode read only
* implementer, `claude-sonnet-5`, effort medium, Claude Code CLI, mode
  write
* implementer bulk, `gemini-3.1-pro-high`, native effort, AGY, mode write,
  only inside a worktree
* code reviewer, `gpt-6-astra`, effort high, Codex CLI, mode read only
* verifier, `claude-opus-5-5`, effort high, Claude Code CLI, mode read and
  execute

The `plan-reviewer` role stops existing. Critiquing the plan becomes the
orchestrator's own requirement gate, which has to approve the plan before
any implementation starts. Independence still holds because the planner
and the orchestrator are different models.

### When the planner actually gets called

Only on CRITICAL tasks. The 65 files under `task/` are acceptance contracts,
not a build sequence. TASK 10, for example, lists six high level steps and a
handful of reference files, and it still needed its own separate plan made
of nine tasks. That plan went through four rounds of findings before it got
approved (`38eda5b`, `2541f30`, `e1583a6`, `703ec1b`, `32766e3`), all of it
before a single line of code existed, which is real evidence that design
review pays off on critical work and that the task file alone does not
replace it.

Outside of CRITICAL, the task file plus the orchestrator's own requirement
gate already is the plan. Calling the planner there would just be wasted
work.

Astra ended up owning the planner and code reviewer roles because it wrote
those 65 task files in the first place. Keeping it on critical planning
keeps things consistent with the contracts it defined itself.

### Astra account budget (Project Hermes)

Planner and code reviewer share the exact same Codex/ChatGPT account limit.
Neither Codex nor Claude Code give programmatic control over extra usage, so
the guarantee comes from three things together, the account not having extra
credit enabled, the wrapper treating a 429 or a "usage limit" message as
BLOCKED without ever retrying on its own, and the instructions flatly
forbidding an upgrade request or swapping the model. At most two Astra
calls per CRITICAL task, one call everywhere else.

### Codex account budget (history)

`gpt-6-astra` and `gpt-5.6-sol` shared the same account and the same limit,
switching between Codex models never actually freed up any quota. Once the
orchestrator moved off Codex, which by far used the most of it since it ran
on every single turn carrying the full context, whatever was left became
limited and predictable, at most two Astra calls per CRITICAL task, one
call everywhere else. The code reviewer only ever got a diff, the
acceptance criteria and a file list, never the whole repo. A spent quota
was always BLOCKED, never a reason to switch models.

## Structural consequence

Right now the Astra roles are native Codex subagents
(`.codex/agents/*.toml`, `exit_code: null`), which only works because Codex
itself is the parent. With Sonnet as the parent instead, Astra becomes a
spawned process like everything else.

Local evidence gathered on September 11 2026

* `codex exec` accepts `-m`, `-c model_reasoning_effort=<effort>`,
  `-s read-only`, `--json`, `--ephemeral`, `--skip-git-repo-check`, and
  emits JSONL events (`thread.started`, `turn.started`, `turn.failed`).
* The `gpt-6-astra` smoke test did not finish, the Codex account had
  already run out of usage. Model identity checking on the Codex stream is
  still NOT PROVEN and needs its own smoke test before that role can be
  called READY.
* `agy` accepts `--mode accept-edits` on top of `--mode plan`, which is
  what makes the writer role possible.
* `claude --safe-mode` turns off skills, plugins and CLAUDE.md entirely.
  `--restricted` on its own still ignores the user settings where plugins
  get enabled. Both were verified to answer NO when asked whether a skill
  was available.
* `--restricted --strict-mcp-config --plugin-dir <dir>` exposes exactly the
  skills sitting inside `<dir>/skills`, confirmed by testing it directly.

## Gemini and Sonnet routing

The `task/COMPLEXIDADE.md` catalog is a hard gate, not a suggestion.

Lane A is the default. IMPORTANT and CRITICAL tasks. Sonnet implements,
Astra reviews, at most one repair round, then the verifier closes it out.

Lane B is for bulk volume only. TRIVIAL and SMALL tasks. Failing RED tests
get written and committed before Gemini ever sees the task, then it
implements inside its own isolated worktree against a plan that names exact
files and boundaries. After that Sonnet runs the tests, checks the result
against the plan and closes whatever gap is left. There is no Astra in this
lane at all, Sonnet acts as the independent reviewer since it did not write
the code.

Lane B gets blocked outright, regardless of the task's classification, when

* the work touches security, migrations, concurrency, recovery,
  credentials or destructive data, Gemini never owns that kind of code
* there are no committed RED tests yet
* there is no dedicated worktree for it

The reasoning behind all of this is recorded evidence, both known Gemini
failures so far were planning failures, required interfaces either got
skipped or contradicted. A tight plan plus a real test oracle removes
exactly that failure mode. It does not remove the fact that some problems
are just hard.

## Repair loop

The loop only exists because the code reviewer rejected something, and it
runs exactly once. The report format stays plain, no rewritten code and no
repeated plan

```
SEVERITY: CRITICAL|HIGH|MEDIUM|LOW
ONDE:     file:line
POR QUE:  one sentence
CORRIGIR: a concrete action
```

If the repair still does not close the finding, it goes up to the
orchestrator to decide. There is no automatic second round. On lane B, the
fallback for a failed repair is Sonnet rewriting the code directly, never a
second attempt from Gemini.

## Keeping token spend low

A shared block the wrapper injects into every spawned role's prompt

* do not repeat context you were already given, the orchestrator is the
  one holding the full history
* reference a file by path and line range, never by dumping it whole
* prefer `rg` and targeted excerpts over reading a file end to end
* run tests with `pytest -q --tb=short` and report only the failures
* never redo research, reading or a test another role already covered
* respect your own role's output ceiling as declared in
  `ROLE_OUTPUT_CEILING`
* long output goes to a file under `artifacts/agents/`, but only for the
  writer roles, since they are the only ones with a write tool at all, read
  only roles just summarize and cite paths with line ranges

The orchestrator is the parent session and never goes through the wrapper,
its own budget rules live in `AGENTS.md`, and it ends up being the biggest
consumer overall simply because it runs on every single turn.

Codex roles keep `--ephemeral` on, isolation wins over caching here, there
is no session reuse at all. Whatever savings show up on the repair loop's
second review come from the payload itself, findings plus the hunks that
actually changed, never the whole diff again. The wrapper reports `usage`
across all three providers, though the Codex side of that extraction still
has not been checked against a real run.

The orchestrator side rules live in the skill itself, pass a commit range,
exact files, open findings and acceptance criteria, never the full history
or a repo dump.

## Skills per role

Every invocation builds a tiny throwaway plugin holding only that role's
skills, symlinked straight from the installed versions. That excludes any
third party hook by construction, which matters because `superpowers`
ships a `session-start` hook that must never run inside a spawned child.

* researcher, verifier: `caveman/caveman`
* planner: `caveman/caveman`, `superpowers/writing-plans`
* implementer: `caveman/caveman`, `mattpocock-skills/engineering/tdd`,
  `superpowers/executing-plans`
* code reviewer: `caveman/caveman`, `mattpocock-skills/engineering/code-review`
* implementer bulk: nothing, AGY keeps `--disable-slash-commands` on

Planner and code reviewer run on Codex, which has no `--plugin-dir`
mechanism, so the wrapper prepends the skill text straight to their prompt
instead of building a plugin. `tools/agents/README.md` is the current
source of truth for what each role actually gets.

A skill that gets declared but is missing from the environment always
results in BLOCKED. There is no silent fallback here, same rule that
already applies to a missing model.

## Write isolation

There are two spawned writer roles, `implementer` and `implementer-bulk`,
plus the orchestrator itself, which writes directly to the main tree. The
wrapper's lock now covers both spawned writer roles. Two writers on the
same working tree is still prohibited, running things in parallel requires
separate worktrees.

## Acceptance criteria

* No role resolves its model or effort from anywhere outside
  `tools/agents/agents.json`.
* The two writer roles are mutually exclusive under the lock.
* A missing Astra role, or one that ran out of quota, always comes back
  BLOCKED, never PASS.
* The skills visible inside a spawned child are exactly the ones declared
  for that role, nothing more.
* No third party plugin hook ever runs inside a spawned child.
* Gemini never receives a task classified IMPORTANT or CRITICAL.
* The repair loop runs at most once per review.
