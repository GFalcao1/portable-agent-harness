# Agent workflow — design rationale

This document is the design history and reasoning behind the multi-agent
harness: why the roster looks the way it does, why Lane B is restricted,
why the repair loop runs once, why token spend needs active management. It
is not the live reference — for the current roster, rules and operational
detail, read `AGENTS.md`, `.agents/skills/multi-agent/SKILL.md` and its
`references/`, and `tools/agents/README.md`.

## Changelog

* Emenda 2026-10-01: code-reviewer moved from Astra to GPT-6.1 Sol (Codex
  CLI, medium); security-reviewer moved off Codex to Fable 5.1 (Claude Code
  CLI, medium). Both reviewers now get only the task idea plus the affected
  file paths and answer a binary verdict (`VERDICT: APPROVED` /
  `VERDICT: REJECTED` with one `file:line | WRONG | FIX` line per blocking
  problem), to cut review tokens. Planner unchanged (Astra).
* Emenda 2026-09-28: roster expanded from the seven-role baseline below to
  the current thirteen-entry matrix (orchestrator plus twelve spawned
  roles). Live roster: `tools/agents/agents.json`. Live role
  responsibilities and contracts:
  `.agents/skills/multi-agent/references/papeis.md`. Budget rule for the
  Codex-based roles updated to match; see
  `.agents/skills/multi-agent/references/orcamento-e-lanes.md`. `agy` was
  installed and both AGY-routed roles passed a smoke test on this date;
  current status and caveats live in `tools/agents/README.md`.
* Emenda 2026-09-19: planner and code-reviewer routing, briefly changed on
  2026-09-18 to a different provider, was reverted the next day back to
  the Codex-routed setup at the same effort levels. `agents.json` and
  `AGENTS.md` are the live source of truth.
* Emenda 2026-09-18 (superseded by the entry above): planner and
  code-reviewer moved off the Codex-routed setup for one day, same effort
  levels, then reverted.

## Goal (2026-09-11 design)

Move orchestration onto a single parent Claude Code session, keep the
bulk-work provider restricted to low-complexity work, cut the cost of every
handoff, and give each role exactly the skills it actually uses, all
without loosening write isolation or ever allowing a silent model swap.

## Role matrix (2026-09-11 baseline — superseded, see `agents.json`)

* orchestrator, parent Claude Code session, mode write
* researcher, Claude Code CLI, mode read only
* planner, Codex CLI, mode read only
* implementer, Claude Code CLI, mode write
* implementer bulk, AGY, mode write, only inside a worktree
* code reviewer, Codex CLI, mode read only
* verifier, Claude Code CLI, mode read and execute

The `plan-reviewer` role stopped existing at this point. Critiquing the plan
became the orchestrator's own requirement gate, which has to approve the
plan before any implementation starts. Independence still holds because the
planner and the orchestrator are different models.

### When the planner actually gets called

Only on CRITICAL tasks. The 65 files under `task/` are acceptance
contracts, not a build sequence. TASK 10, for example, listed six high
level steps and a handful of reference files, and it still needed its own
separate plan made of nine tasks. That plan went through four rounds of
findings before it got approved, all of it before a single line of code
existed — real evidence that design review pays off on critical work and
that the task file alone does not replace it.

Outside of CRITICAL, the task file plus the orchestrator's own requirement
gate already is the plan; calling the planner there would be wasted work.

The Codex-based provider ended up owning the planner and code reviewer
roles because it wrote those 65 task files in the first place. Keeping it
on critical planning keeps things consistent with the contracts it defined
itself.

### Codex-based role account budget — rationale

Planner and code reviewer share the exact same Codex/ChatGPT account limit.
Neither Codex nor Claude Code give programmatic control over extra usage,
so the guarantee comes from three things together: the account not having
extra credit enabled, the wrapper treating a 429 or a "usage limit" message
as BLOCKED without ever retrying on its own, and the instructions flatly
forbidding an upgrade request or a model swap. Current budget numbers:
`.agents/skills/multi-agent/references/orcamento-e-lanes.md`.

### Codex account budget (history)

Two Codex-hosted models originally shared the same account and the same
limit, so switching between them never freed up any quota. Once the
orchestrator moved onto a Claude Code parent session, which by far used the
most of that budget since it ran on every single turn carrying the full
context, whatever was left became limited and predictable. The code
reviewer only ever got a diff, the acceptance criteria and a file list,
never the whole repo. A spent quota was always BLOCKED, never a reason to
switch models.

## Structural consequence

At the point of this redesign, the Codex-routed roles were native Codex
subagents (`.codex/agents/*.toml`, `exit_code: null`), which only worked
because Codex itself was the parent. With a Claude Code session as the
parent instead, those roles became spawned processes like everything else.

Local evidence gathered on 2026-09-11:

* `codex exec` accepts `-m`, `-c model_reasoning_effort=<effort>`,
  `-s read-only`, `--json`, `--ephemeral`, `--skip-git-repo-check`, and
  emits JSONL events (`thread.started`, `turn.started`, `turn.failed`).
* The Codex-based role smoke test did not finish that day; the linked
  account had already run out of usage. Model identity checking on the
  Codex stream needed its own smoke test before that role could be called
  READY.
* The AGY-routed writer accepts `--mode accept-edits` on top of
  `--mode plan`, which is what makes the writer role possible.
* `claude --safe-mode` turns off skills, plugins and CLAUDE.md entirely.
  `--restricted` on its own still ignores the user settings where plugins
  get enabled. Both were verified to answer no when asked whether a skill
  was available.
* `--restricted --strict-mcp-config --plugin-dir <dir>` exposes exactly the
  skills sitting inside `<dir>/skills`, confirmed by testing it directly.

## Lane A / Lane B routing rationale

`task/COMPLEXIDADE.md` is a hard gate, not a suggestion. Lane A is the
default for IMPORTANT and CRITICAL work: the implementer role implements, a
Codex-based reviewer reviews, at most one repair round, then the verifier
closes it out. Lane B is for bulk volume only, TRIVIAL and SMALL tasks:
failing RED tests get written and committed first, the AGY-routed worker
implements inside its own isolated worktree against a plan naming exact
files and boundaries, then the implementer role runs the tests, checks the
result against the plan and closes whatever gap is left — no Codex-based
role in this lane at all, since the implementer acts as the independent
reviewer for code it did not write.

The reasoning behind the Lane B restrictions is recorded evidence: known
AGY-worker failures so far were planning failures, where a required
interface either got skipped or contradicted. A tight plan plus a real test
oracle removes exactly that failure mode; it does not remove the fact that
some problems are just hard. Current lane rules and blockers:
`.agents/skills/multi-agent/references/orcamento-e-lanes.md`.

## Repair loop rationale

The loop only exists because a reviewer rejected something, and it runs
exactly once by design — repeating rounds hides a plan or scope problem
instead of fixing it. On Lane B, the sanctioned fallback for a failed
repair is the implementer role rewriting the code directly, never a second
attempt from the AGY-routed worker. Current format and mechanics:
`.agents/skills/multi-agent/references/repair-e-validacao.md`.

## Keeping token spend low — rationale

Handoffs got expensive because early runs repeated full history and pasted
whole files instead of referencing paths and line ranges. The parent
session is the biggest consumer overall simply because it runs on every
single turn; Codex-routed roles stay ephemeral by design, isolation wins
over caching there. Whatever savings show up on the repair loop's second
review come from sending only the changed hunks, never the whole diff
again. Current operational rules: `.agents/skills/multi-agent/SKILL.md`
("Economia de tokens").

## Skills per role — rationale

Every invocation builds a tiny throwaway plugin holding only that role's
skills, symlinked straight from the installed versions. That excludes any
third party hook by construction, which matters because `superpowers`
ships a `session-start` hook that must never run inside a spawned child. A
skill that gets declared but is missing from the environment always
results in BLOCKED, same rule that already applies to a missing model.
Current skill-per-role mapping: `tools/agents/README.md`.

## Write isolation

At the point of this redesign there were two spawned writer roles plus the
orchestrator writing directly to the main tree, and the wrapper's lock
covered both. Two writers on the same working tree was already prohibited;
running things in parallel required separate worktrees. That invariant
still holds for the current three spawned writer roles — see
`.agents/skills/multi-agent/references/paralelismo.md`.

## Success criteria for this redesign (met, kept for record)

No role resolved its model or effort from anywhere outside
`tools/agents/agents.json`; the writer roles were mutually exclusive under
the lock; a missing or exhausted Codex-based role always came back BLOCKED,
never PASS; the skills visible inside a spawned child were exactly the ones
declared for that role; no third party plugin hook ever ran inside a
spawned child; the bulk-work provider never received a task classified
IMPORTANT or CRITICAL; the repair loop ran at most once per review. These
are now standing invariants — see `AGENTS.md`.
