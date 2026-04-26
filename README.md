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

Pre-v0.1.0. Bootstrapped; no functional code yet. See
[`docs/plan.md`](docs/plan.md) for phasing.

## Repo orientation

```
drive-workspace/
├── backend/                 Python package + reference Flask server
├── android/                 Gradle project: library + tester app
├── integration-tests/       End-to-end tests against real Drive
├── docs/
│   ├── architecture.md      What we're building (start here)
│   ├── plan.md              Phases, tasks, what's next
│   ├── decisions/           ADRs — why we made each non-obvious choice
│   └── sessions/            Per-session task briefs
├── docker-compose.yml       Local dev stack
└── README.md
```

## Reading order for new contributors

1. [`docs/architecture.md`](docs/architecture.md) — the picture, ~5 pages
2. [`docs/decisions/`](docs/decisions/) — scan titles, read what's relevant
3. [`docs/plan.md`](docs/plan.md) — current phase + task list
4. [`docs/sessions/`](docs/sessions/) — find the brief for the task you're picking up

## License

Proprietary. In-house use only. See [`LICENSE`](LICENSE).
