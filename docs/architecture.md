# Architecture

> **Status**: canonical. Updated only when an ADR changes a structural choice.
> **Audience**: anyone — human or model — picking up work in this repo.

---

## 1. Purpose

`drive-workspace` is reusable plumbing for the pattern *"a fleet of mobile
devices captures media in the field, and that media must end up in an
org-controlled Google Drive — reliably, offline-tolerantly, and without ever
putting a Drive credential on a device."*

It is **not** a turnkey product. It is a backend Python package + an Android
client library + a reference server that demonstrates how the two fit
together. A host application (SmartMeter, hypothetical-property-inspection,
etc.) writes ~100 lines of glue and gets the full upload pipeline.

The first real consumer will be SmartMeter; the architecture is shaped so that
the *second* consumer is easy.

## 2. Three concerns

The system has exactly three responsibilities. Anything else belongs to the
host app.

| Concern               | What it does                                                                  |
|-----------------------|-------------------------------------------------------------------------------|
| **Folder lifecycle**  | Provision a per-principal folder + spreadsheet from a template; share it view-only with the principal's Google account; revoke on offboarding. |
| **Upload sessions**   | Mint resumable upload URLs (single or batched) routed into the right per-principal subfolder; do the actual chunked PUT from the device. |
| **Spreadsheet log**   | Append a row per host-defined event (e.g. survey submission) with hyperlinks to the just-uploaded media. |

If a feature doesn't fit one of these three buckets, it does not belong here.

## 3. Trust boundary

The single most important architectural decision: **the device never holds a
Drive credential.** All Drive authority lives on the backend.

```
┌─────────────────────┐       ┌──────────────────────┐       ┌─────────────────┐
│  Android device     │  (1)  │  Host backend        │  (2)  │  Google Drive   │
│  library            │──────▶│  + drive_workspace   │──────▶│  v3 API         │
│                     │       │                      │       │                 │
│  • host's auth      │       │  • SA credential     │       │                 │
│    headers only     │       │  • OAuth2 token      │       │                 │
│                     │◀──────│    (server-cached)   │◀──────│                 │
│                     │ URL   │                      │ URL   │                 │
└─────────────────────┘       └──────────────────────┘       └─────────────────┘
        │                                                            ▲
        └──────────────── (3) PUT chunks directly ───────────────────┘
                              via opaque upload URL
```

Three legs, three credential surfaces:

1. **Device → Backend** uses the host app's existing auth (e.g. device token
   + bearer JWT). The library is unaware; the host's interceptors attach
   headers.
2. **Backend → Drive** uses the service-account credential, server-side only,
   loaded via a host-pluggable `Authenticator`.
3. **Device → Drive** carries no auth header. The resumable session URL is
   self-authorizing for one specific file size at one specific path, expires
   in ~7 days, and is opaque to the library.

See [`decisions/0001-backend-mediated-uploads.md`](decisions/0001-backend-mediated-uploads.md).

## 4. Storage layout (Drive)

Org-owned root, three regions:

```
/<root_folder>/
├── Master/                              ← processed/aggregated data; office-only
├── Templates/
│   └── PrincipalFolderTemplate/         ← canonical structure copied per onboard
│       ├── photos/
│       ├── audio/
│       ├── videos/
│       └── log.gsheet                   ← template spreadsheet
└── Principals/
    ├── alice/                           ← shared view-only with alice@org.com
    │   ├── photos/
    │   ├── audio/
    │   ├── videos/
    │   └── alice_log.gsheet
    └── bob/
        └── ...
```

- The principal sees their folder via drive.google.com on any device they're
  signed in with — no app-specific sign-in needed.
- The principal **cannot delete, rename, or modify** files (view-only share).
- The org can move/audit/archive freely; nothing is owned by the principal.

See [`decisions/0002-per-principal-folders-org-owned.md`](decisions/0002-per-principal-folders-org-owned.md).

## 5. Upload flow (single file)

```
Device                      Backend                       Drive
  │                            │                            │
  │ 1. capture file locally    │                            │
  │ 2. write survey row to     │                            │
  │    local DB (host's,       │                            │
  │    not the library's)      │                            │
  │                            │                            │
  │  POST initiate(file meta)  │                            │
  ├───────────────────────────▶│                            │
  │                            │ resolve principal_id       │
  │                            │ → folder_id + subfolder    │
  │                            │ POST /upload?resumable     │
  │                            ├───────────────────────────▶│
  │                            │       Location: <url>      │
  │                            │◀───────────────────────────┤
  │   { upload_url,            │                            │
  │     drive_file_id,         │                            │
  │     expires_at }           │                            │
  │◀───────────────────────────┤                            │
  │                                                         │
  │  PUT chunks (1 MB) with Content-Range                   │
  ├────────────────────────────────────────────────────────▶│
  │  ◀── 308 Resume Incomplete (between chunks) ────────────│
  │  ◀── 200 OK with file metadata (final chunk) ───────────│
  │                                                         │
  │ store drive_file_id in local DB                         │
  │ next sync forwards survey row + drive_file_id to backend│
  │                                                         │
  │                            │  later: backend appends    │
  │                            │  spreadsheet row with      │
  │                            │  =HYPERLINK(file_id) cells │
```

Resumable behavior:
- Library checkpoints byte-offset to a small library-owned Room DB after each
  acknowledged chunk.
- App kill mid-transfer → on next call, library queries the server's
  acknowledged offset and resumes.
- 410/404 from Drive → library re-calls `initiate`, gets a fresh URL,
  starts a fresh session.
- 5xx / 429 → exponential backoff with jitter; honors Retry-After.

See `android/library/README.md` (post-Phase-1) for the wire-level details.

## 6. Backend offline tolerance — session prefetch bank

A device that can reach Drive but not the host backend can still upload, via
**pre-minted upload sessions** drawn from a local bank.

```
Morning sync (backend reachable):
  Device → POST /api/drive/initiate-upload?count=30
  Backend → mints 30 resumable sessions, returns array
  Library → stashes them in checkpoint DB

Daytime (backend unreachable, Drive reachable):
  Device captures file → library pulls a session from the bank
  Library uploads to Drive directly. No backend round-trip.

Evening (backend reachable again):
  Library refills the bank.
  Sessions older than 7 days are pruned.
```

This is a small extension on top of the basic flow, not a separate code path.
See [`decisions/0003-session-prefetch-bank.md`](decisions/0003-session-prefetch-bank.md).

## 7. Component view (backend package)

```
┌──────────────────────────────────────────────────────────────────┐
│                       drive_workspace                             │
│                                                                   │
│   DriveWorkspace  ─┬─▶ FolderManager     ──┐                     │
│                    │                       │                     │
│                    ├─▶ UploadSessionMint  ─┼─▶ Drive REST API    │
│                    │                       │                     │
│                    ├─▶ SpreadsheetLogger  ─┴─▶ Sheets REST API   │
│                    │                                              │
│                    └─▶ ReconciliationRunner                       │
│                                                                   │
│   Plug points (host implements):                                  │
│     • PrincipalStore   — persistence (default: SQLAlchemy)       │
│     • Authenticator    — SA credential loader                    │
│     • LogSchema        — spreadsheet column definitions          │
│                                                                   │
│   Optional adapters:                                              │
│     • drive_workspace.adapters.flask.make_blueprint(...)         │
└──────────────────────────────────────────────────────────────────┘
```

The host writes:
- **`PrincipalStore`** (~30 lines) — wraps host's existing user table.
- **`LogSchema`** (~15 lines) — declares spreadsheet columns + row mapping.
- **3 Flask routes** OR **`make_blueprint(...)`** invocation (~20 lines).
- **`Authenticator`** — a one-liner usually (file path or secret-manager ARN).

Total host glue: ~80 lines.

See [`decisions/0004-modular-package-with-host-plugins.md`](decisions/0004-modular-package-with-host-plugins.md).

## 8. Public API sketch (backend)

```python
from drive_workspace import DriveWorkspace, FileSpec, Authenticator

dw = DriveWorkspace(
    auth=Authenticator.from_file("/secrets/drive-sa.json"),
    root_folder_id="0AB...",
    shared_drive_id="0AS...",          # ADR-0011: every Drive call carries this
    template_folder_id="1tpl...",
    template_spreadsheet_id="1tps...",
    principal_store=MyPrincipalStore(db),
    log_schema=MyLogSchema(),
)

# Onboarding
dw.principals.provision(
    principal_id="alice",
    display_name="Alice Example",
    grant_view_to_email="alice@org.com",
)

# Single or batched upload sessions
sessions = dw.uploads.initiate(
    principal_id="alice",
    files=[
        FileSpec(file_name="img.jpg", mime_type="image/jpeg",
                 file_size_bytes=4_194_304, kind="photo"),
    ],
)

# Spreadsheet row append (host-defined columns)
dw.logs.append(
    principal_id="alice",
    row={"timestamp": "...", "photo_id": "1xyz", "status": "submitted"},
)

# Offboarding
dw.principals.revoke("alice")
```

## 9. Public API sketch (Android)

```kotlin
interface DriveUploader {
    fun upload(localFile: File, request: UploadRequest): Flow<UploadProgress>
}

fun interface UploadInitiator {
    suspend fun initiate(request: UploadRequest): UploadSession
}
```

The host app provides `UploadInitiator` (which calls the backend's
`initiate-upload` endpoint); everything else is provided by the library.
See `android/library/README.md` (post-Phase-1) for full surface.

## 10. Repo layout

```
drive-workspace/
├── backend/
│   ├── drive_workspace/         # the importable package
│   │   ├── workspace.py
│   │   ├── folders.py
│   │   ├── uploads.py
│   │   ├── logs.py
│   │   ├── reconcile.py
│   │   ├── stores/
│   │   │   ├── protocol.py
│   │   │   └── sqlalchemy.py
│   │   ├── adapters/
│   │   │   └── flask.py
│   │   └── tests/
│   ├── reference_server/        # thin Flask demo wrapping the package
│   ├── pyproject.toml
│   └── README.md
├── android/
│   ├── library/                 # the upload library (~ what was :core:drive)
│   ├── tester/                  # the standalone harness
│   ├── settings.gradle.kts
│   └── build.gradle.kts
├── integration-tests/           # E2E against real Drive (CI-only)
├── docs/
│   ├── architecture.md          # this file
│   ├── plan.md
│   ├── decisions/               # ADRs
│   └── sessions/                # per-session task briefs
├── docker-compose.yml           # postgres + reference_server, local dev
├── .github/workflows/           # backend-ci, android-ci, e2e
└── README.md
```

See [`decisions/0005-monorepo-three-subtrees.md`](decisions/0005-monorepo-three-subtrees.md).

## 11. Stack at a glance

| Layer                | Choice                            | ADR  |
|----------------------|-----------------------------------|------|
| Backend language     | Python 3.11+                      | 0006 |
| Backend HTTP         | Flask + Flask-RESTX (sync)        | 0006 |
| Backend persistence  | SQLAlchemy (default impl); host can override | 0004 |
| Reference DB         | Postgres (in docker-compose)      | 0006 |
| Type checking        | `mypy --strict` from day one      | 0006 |
| Lint                 | ruff                              | 0006 |
| Android language     | Kotlin 2.0.x                      | —    |
| Android HTTP         | OkHttp                            | —    |
| Android persistence  | Room (library-owned, single table)| —    |
| Test stack (BE)      | pytest, responses                 | 0006 |
| Test stack (Android) | JUnit + MockWebServer + Robolectric (Room) | — |

## 12. What is explicitly out of scope

- **Anything the host's domain knows.** No "survey," no "inspection,"
  no "appointment." `principal_id` is the most domain-specific token the
  package will ever name.
- **Authn/authz on the wire.** Host's middleware decides who can call
  `initiate-upload`. The package trusts that the request is authenticated.
- **Scheduling.** Reconciliation ships as a CLI; the host's cron / k8s
  CronJob / Celery beat decides cadence.
- **Other storage backends.** Drive only. If Azure Blob or S3 are wanted,
  fork the package; do not pollute `drive_workspace` with abstraction
  layers we don't need today.
- **Async runtime.** Sync Flask. Re-evaluate if QPS demands it.
- **Open-sourcing.** Proprietary, in-house only.

## 13. How this document evolves

- Structural changes require an ADR. The ADR comes first, then this doc is
  updated to reflect the decided state.
- Cosmetic / clarification edits don't require an ADR; just commit.
- The plan ([`plan.md`](plan.md)) tracks "what we're doing next." This
  document tracks "what we are." Don't conflate them.
