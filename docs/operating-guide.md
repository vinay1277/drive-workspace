# Operating Guide — How you actually work this repo

> **Audience**: you (the human running this project).
> **Purpose**: practical, day-to-day workflow. Not architecture, not rationale.
> **Companion to**: [`architecture.md`](architecture.md) (what we're building),
> [`plan.md`](plan.md) (what's next),
> [`decisions/0007-docs-as-memory-sessions-as-workers.md`](decisions/0007-docs-as-memory-sessions-as-workers.md) (why we work this way).

---

## TL;DR

```
Day starts:
  1. Open D:\drive-workspace in your editor.
  2. Read plan.md → find the next "not started" task.
  3. Read or write the session brief in docs/sessions/.
  4. Open a fresh Claude Code window in D:\drive-workspace.
  5. Paste the kickoff prompt (template below). Send.
  6. Watch the model confirm its plan. Approve or correct.
  7. Let it work. Intervene only if it goes off-script.

Session ends:
  8. Verify Definition-of-Done items pass.
  9. Confirm `git log` shows reasonable commits.
  10. Confirm plan.md is updated and brief's "Outcome" section is filled.
  11. Close the Claude Code window. Do not "continue tomorrow" in it.

Next session:
  Repeat. Write a new brief if the next task doesn't have one.
```

That's the whole loop. The rest of this document expands each step.

---

## 1. Your role in three hats

You wear three hats across the lifetime of this project. Knowing which hat
you're wearing at any given moment makes decisions easier.

| Hat | When | What you do |
|-----|------|-------------|
| **Architect** | Rarely now (we did most of it in the bootstrap conversation). | Decide structural questions; write or commission ADRs. |
| **Director** | At the start and end of every session. | Pick the next task; write or read the brief; verify done-ness. |
| **Reviewer** | During and after each session. | Sanity-check what the model produced; spot scope creep; catch wrong-headed implementations early. |

You are **not** the implementer. The model is. Your job is to make sure the
implementer has clear instructions and produces work that meets the bar.

If you find yourself writing code in this repo, ask whether you should be
writing a session brief instead.

---

## 2. The session lifecycle, step by step

### 2.1 Before opening Claude Code

1. **Open the repo in your editor** (VS Code, IntelliJ, whatever).
   Have these tabs open:
   - `docs/plan.md`
   - `docs/architecture.md`
   - The session brief you're about to run
2. **Pick the task.** It's the next "not started" item under the current
   phase in `plan.md`.
3. **Find or write the brief.**
   - If a brief already exists in `docs/sessions/` for this task, open it
     and re-read it.
   - If not, copy `docs/sessions/_template.md` to a new file named
     `YYYY-MM-DD-<short-slug>.md` and fill it out. **Writing the brief is
     part of the work.** It forces you to be specific about what's in
     scope and what "done" means.

### 2.2 Open a fresh Claude Code session

**Always open a new session.** Never resume a previous one. Per ADR-0007,
prior sessions' context is not your friend — the docs are.

On Windows (PowerShell or Terminal):

```powershell
cd D:\drive-workspace
claude
```

If you have multiple Claude Code installations, make sure the one you launch
is the one with your model preference. (Sonnet for routine work, Opus for
gnarly architectural moments.)

### 2.3 Paste the kickoff prompt

Use this template (adjust the brief filename for the session you're running):

```
You're picking up <task name> in the drive-workspace project.

The repo is your current working directory. Read these files first, in
order, before writing any code:

1. docs/architecture.md (skim if you've read it; full read if not)
2. docs/plan.md
3. docs/sessions/<YYYY-MM-DD-task-slug>.md  ← your brief
4. The ADRs your brief lists as required reading

Do not read prior session transcripts. If a decision isn't in the docs,
treat it as not yet made and ask before deciding.

Operational rules:
- The brief's "Definition of done" is the contract.
- The brief's "Out of scope" list is binding. If tempted, add to plan.md
  instead.
- Architectural changes require a new ADR before code (use the template
  at docs/decisions/_template.md). Pause for my confirmation.
- Make one commit per logical chunk.
- When done: update plan.md, fill in the brief's "Outcome" section,
  final commit references the brief filename.

Confirm your plan against the brief's Definition of done before writing
code.
```

Save this template somewhere reusable (a `kickoff.txt` in your home
directory, a snippet in your editor, whatever's frictionless).

### 2.4 During the session

The model will read the docs and propose a plan. **Read the plan.** This is
the one moment where five minutes of your attention prevents an hour of
rework.

Things to look for:

| Healthy | Unhealthy |
|---------|-----------|
| Plan matches the brief's Definition of done. | Plan adds tasks not in the brief. |
| Asks you about open questions in the brief. | Picks unilaterally. |
| Reads the ADRs before deciding. | Re-derives architecture. |
| Touches files listed in "In scope." | Touches files not listed. |
| Makes one commit per chunk with clear messages. | One mega-commit at the end, or never commits. |

If the plan looks right, say "go" or "proceed." If not, push back specifically:
"Don't do task 3, that's out of scope" or "task 1 needs an ADR first."

While it's working, you don't need to watch every tool call. Glance at:
- File-write notifications: are the paths sensible?
- Commit messages: do they match what was supposed to happen?
- Any errors or "I think we should also..." moments — those are scope-creep
  signals.

### 2.5 When the session reports done

The model will say something like "Phase 1 complete." Don't take its word
for it. Verify:

```powershell
cd D:\drive-workspace
git log --oneline                   # Do the commits make sense?
git status                          # Anything uncommitted?
```

Then check the brief's Definition of Done items one by one. For Phase 1, that
means actually running:

```powershell
docker compose up                   # Does it boot?
curl http://localhost:8080/health   # Does it respond?
cd android && .\gradlew :tester:installDebug
```

If a Definition-of-Done item doesn't pass, the session is **not done**. Tell
the model what failed, let it fix.

### 2.6 Closing the session

Once verified:

1. Confirm `docs/plan.md` has the completed tasks marked.
2. Confirm the session brief's "Outcome" section is filled in with what
   shipped.
3. Push commits if you have a remote set up.
4. **Close the Claude Code window.** Do not save the session for "tomorrow."
   Tomorrow gets a fresh window with a fresh brief.

---

## 3. Writing the next brief

Briefs are written **before** the session that runs them, by you. They take
~10 minutes to write well and save 10× that in misdirected work.

The template at `docs/sessions/_template.md` has every section. The two
hardest sections to get right:

**"In scope"** should list specific files or modules. Not "implement
folder lifecycle" but "implement `drive_workspace/folders.py:FolderManager`
with `provision`, `revoke`, `archive` methods."

**"Definition of done"** should be checkable. Not "code works" but
"`pytest backend/drive_workspace/tests/test_folders.py` passes" or
"`curl <url>` returns `{...}`." If you can't write a check, the criterion
is too vague.

When you're stuck on a brief, look at
`docs/sessions/2026-04-26-phase1-skeleton.md` — it's verbose because it's
the first one, but the structure is solid.

---

## 4. Multi-session bookkeeping

You will lose track of where you are. That's fine; the system is designed for
it. Recovery:

1. `git log --oneline -20` — what's recently happened?
2. Open `docs/plan.md` — what's marked done? What's next?
3. Open the most recent file in `docs/sessions/` — what was the last task,
   and did its "Outcome" section get filled in?

If "Outcome" is empty on a recent brief, the session that ran it didn't
close cleanly. Either pick up where it left off (write a follow-up brief
referencing the same task) or declare it bankrupt and rewrite the brief.

You do not need a calendar, a project tracker, or anything else. `plan.md`
is your tracker; commits are your timeline; briefs are your work units.

---

## 5. Things to watch for

### 5.1 Scope creep

The single most common failure mode. Symptoms:
- Model says "while I'm in here, I noticed..."
- Files outside the brief's "In scope" list are being modified.
- New ADRs being written without your having asked.

**Action**: stop the session. Either (a) the new work is genuinely needed —
add it to `plan.md` for a future session, or (b) it's a distraction — say
no and refocus.

### 5.2 Decision drift

Symptoms:
- Model is debating an architectural choice that's already in an ADR.
- Code doesn't match the architecture document.

**Action**: point at the specific ADR or architecture section. "This is
decided in ADR-0002. Implement to that spec or write a superseding ADR
first."

### 5.3 Half-finished sessions

Symptoms:
- Definition-of-Done items don't pass.
- `git status` shows uncommitted files.
- Model says "I'll let you commit this."

**Action**: don't accept the session as done. Either get to clean state in
this session, or open a follow-up brief that explicitly picks up the
half-done state.

### 5.4 Skipping the docs

Symptoms:
- Model proposes architecture that's already decided.
- Model implements without reading the brief.
- Model treats the docs as optional context.

**Action**: this means the kickoff prompt didn't take. Stop, restate the
required-reading order, and ask it to confirm what it read before
proceeding.

---

## 6. When something goes badly wrong

### 6.1 You realize a session went off the rails halfway through

Stop the session. `git reset --hard` to the last good commit. Open a fresh
session with a more specific brief explaining the constraint that was
violated.

### 6.2 You realize an architectural decision was wrong

Don't quietly change it. Write a new ADR that supersedes the old one, then
update `architecture.md` and any code in a session devoted to the migration.

### 6.3 You lose track of what's deployed / what's in main / what's local

`git log --all --oneline --graph -20` is usually enough. If not,
`git status` per worktree.

### 6.4 You want to try two approaches in parallel

Use git worktrees. From repo root:

```powershell
git worktree add ../drive-workspace-experiment -b experiment/<name>
cd ..\drive-workspace-experiment
claude
```

Different worktree = different working directory = different Claude session
won't conflict with the main one. Merge or discard the experiment branch
when done.

---

## 7. Common questions

**Q: How long should a session be?**
A: 30 minutes for small tasks, 2 hours for medium ones. If you're at 4
hours, you should have ended an hour ago. Briefs that don't fit in 2 hours
should be split.

**Q: Should I read the model's chain of thought during a session?**
A: Glance, don't deep-read. Trust the docs to constrain the work; verify
output, not process.

**Q: What if I want to discuss design with the model, not implement?**
A: That's a different kind of session — a "design session" rather than an
"implementation session." Use a brief that says so explicitly: "Goal:
produce ADR draft for X. No code." Discuss freely; output is a markdown
file.

**Q: How do I know when to add a new ADR?**
A: When you find yourself making a decision that affects the structure of
the system, will outlive a single session, and would surprise a future
contributor. If unsure, write the ADR — they're cheap.

**Q: How do I know when to update architecture.md?**
A: After ADR-driven structural changes. Not for every tweak. The doc should
describe the system as it is, not as it once was.

**Q: What if the model and I disagree on an approach?**
A: It's deferring to you by default. State your preference clearly and ask
it to follow. If it pushes back with a substantive reason, weigh it — the
model occasionally catches things you didn't. But you're the architect; you
get the final call.

**Q: Can I skip writing briefs for "small" tasks?**
A: Yes, for genuinely small ones (a typo fix, a one-line config change).
But anything that takes more than 15 minutes deserves a brief. The brief is
how you remember why you did it.

---

## 8. The shape of a good week

Mon: write briefs for the week's work (30 min)
Tue–Thu: run sessions, one task per session, verify each
Fri: review what shipped; update plan.md; write briefs for next week
Weekend: ignore the project

The cadence isn't fixed; the discipline is. Plan, execute, verify, repeat.
