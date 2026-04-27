# drive-workspace

Reusable plumbing for "field app uploads media to org-owned Google Drive."

A standalone backend Python package + Android client library + reference server,
designed to drop into any application that needs:

- Per-user (per-"principal") folder structure inside an org-owned Drive
- Resumable, offline-tolerant uploads from mobile to Drive
- A backend that mints upload sessions but never sees the bytes
- A spreadsheet log per principal with one-click hyperlinks to media

The Android library [`:library`](android/library/) holds zero Drive credentials.
The backend package [`drive_workspace`](backend/drive_workspace/) holds the
service-account key and mints short-lived per-file resumable URLs that the
device PUTs to directly. See [`docs/architecture.md`](docs/architecture.md).

## Status

Pre-v0.1.0. Phase 1 + Phase 2A complete; Phase 2B (real Drive) unblocked
via Path B 2.0 (Workspace + Shared Drive operational). See
[`docs/plan.md`](docs/plan.md) for phasing and
[`docs/deployment.md`](docs/deployment.md) for the live test bed.

## Repo orientation

```
drive-workspace/
├── backend/                 Python package + reference Flask server
├── android/                 Gradle project: library + tester app
├── integration-tests/       End-to-end tests against real Drive
├── docs/
│   ├── architecture.md      What we're building (start here)
│   ├── plan.md              Phases, tasks, what's next
│   ├── deployment.md        Live test-bed state (Workspace, Shared Drive, IDs)
│   ├── troubleshooting.md   Concrete failures + fixes (search this when stuck)
│   ├── operating-guide.md   How to work the repo, session by session
│   ├── decisions/           ADRs — why we made each non-obvious choice
│   └── sessions/            Per-session task briefs
├── SUPPORT.md               How to get help / open issues
├── docker-compose.yml       Local dev stack
└── README.md
```

## Reading order for new contributors

1. [`docs/architecture.md`](docs/architecture.md) — the picture, ~5 pages
2. [`docs/decisions/`](docs/decisions/) — scan titles, read what's relevant
3. [`docs/plan.md`](docs/plan.md) — current phase + task list
4. [`docs/sessions/`](docs/sessions/) — find the brief for the task you're picking up

## Day-to-day workflow

[`docs/operating-guide.md`](docs/operating-guide.md) is the practical guide
for running this project session by session — how to start a session, what
to watch for, how to verify done-ness, how to write briefs.

## I'm a developer integrating this — where do I start?

If you're looking to use `drive-workspace` from a host application
rather than contribute to it:

1. [`SUPPORT.md`](SUPPORT.md) — self-serve doc map + how to ask questions.
2. [`docs/architecture.md`](docs/architecture.md) — the model (5 pages).
3. [`integration-tests/smartmeter/`](integration-tests/smartmeter/) — a
   working sketch of what host glue looks like (~80 lines).
4. [`docs/troubleshooting.md`](docs/troubleshooting.md) — search here
   when you hit an error.

## License

Proprietary. In-house use only. See [`LICENSE`](LICENSE).
