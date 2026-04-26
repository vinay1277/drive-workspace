# ADR-0007: Docs as memory, sessions as workers

- **Status**: accepted
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

This project will be built across many short Claude Code sessions, possibly
with multiple people on different days. Two failure modes loom:

1. **One giant rolling session**: context bloat, expensive per turn,
   amnesia about decisions actually made.
2. **Fresh sessions with no anchor**: every session re-debates settled
   questions because the rationale only lives in old transcripts.

Either way, decisions trapped inside chat transcripts are decisions that
will be re-litigated.

## Decision

Decisions live in the repo, not in conversations. Three permanent doc
classes plus a rolling session class:

| Doc class | Stability | Purpose |
|-----------|-----------|---------|
| `architecture.md` | Stable; changes via ADR | What we are building. |
| `decisions/NNNN-*.md` (ADRs) | Append-only | Why we chose what we chose. Superseded, never deleted. |
| `plan.md` | Updated each session | What's done, what's next, what's blocked. |
| `sessions/YYYY-MM-DD-*.md` | Per-session | The brief that scopes a single session's work. |

A new session reads `architecture.md`, scans relevant ADRs, opens its
session brief, and starts work. **It does not read prior session
transcripts.** If something needed to carry forward, it should have been
captured in the docs.

## Consequences

**Positive**:
- Sessions are cheap and substitutable. A new contributor (or a fresh
  Claude) can pick up work on day 60 without reading 20 transcripts.
- Token cost per session stays small.
- Decisions that survive contact with reality become institutional
  knowledge; decisions that don't get superseded ADRs.
- "Why are we doing this?" has a one-link answer.

**Negative**:
- Discipline cost: every non-trivial decision must be written up. The
  temptation to "just decide it in the conversation" is real. Counter:
  if it isn't worth a paragraph in an ADR, it isn't worth deciding in this
  conversation either.
- Fresh-session warmth: a new session has to load the architecture doc,
  which is slower than continuing an existing session. Worth it.

## Operational rules

1. **Architectural changes** require an ADR before code lands. The ADR is
   the change-control mechanism.
2. **Ad-hoc decisions** that turn out to be load-bearing get retroactive
   ADRs the moment they're recognized. Don't let unwritten rules accumulate.
3. **Session briefs** are the prompt for the next Claude (or human). They
   list: goal, deliverables, in-scope files, out-of-scope, definition of
   done, links to relevant ADRs and architecture sections. ~1 page.
4. **Don't continue a session past its brief.** When the brief's tasks are
   done, end the session. The temptation to "while I'm here, also fix..."
   is the trap.

## Implementation notes

- ADR template lives in `decisions/_template.md` (to be added in the next
  session if not by Phase 1 close).
- Session-brief template lives in `sessions/_template.md` (same).
- `plan.md` is the only document anyone needs to look at to know "what's
  next." Keep it tight; no historical narrative.
