# ADR-0010: Library dispatcher discipline for host-supplied callbacks

- **Status**: proposed (decision pending)
- **Date**: 2026-04-26
- **Supersedes**: —

## Context

During Phase 1 verification, the tester app's `BackendInitiator.initiate()`
ran synchronous OkHttp on the main thread, throwing
`NetworkOnMainThreadException`. Root cause: the `Flow` returned by
`DriveUploader.upload(...)` runs on the collector's dispatcher
(`viewModelScope` defaults to `Dispatchers.Main`), and `DriveUploaderImpl`
calls `initiator.initiate(request)` directly inside the flow body — so
any sync work the host does in its initiator implementation lands on
whatever dispatcher the host happened to be collecting on. See
[`sessions/2026-04-26-phase1-skeleton.md`](../sessions/2026-04-26-phase1-skeleton.md)
"Follow-up verification".

The library separately had its own copy of this footgun in
`ResumableUploadEngine.executeAsync` (`runInterruptible { ... }` without
specifying a dispatcher inherits the caller's context). That bug was a
clear library-side fix (commit `c03a4b1`).

The question this ADR captures is the *first* one: **should the library
defensively dispatch the host-supplied `UploadInitiator.initiate()` call
to `Dispatchers.IO` on behalf of the host, so future host
implementations cannot hit the same NetworkOnMainThread exception?**

## Decision required

Two options:

1. **Library auto-dispatches** — `DriveUploaderImpl.runUpload` wraps the
   `initiator.initiate(request)` call in `withContext(Dispatchers.IO)`.
   Hosts can write naïve sync HTTP in their initiators without crashing.
2. **Host owns the dispatcher** — the library treats `initiate` as just
   a `suspend fun` with whatever semantics suspend functions have on
   Android (i.e. "you better know which dispatcher you're on"). Host
   implementations must do their own `withContext(Dispatchers.IO)` if
   they call sync I/O.

### Arguments for #1 (library dispatches)

- The most common host implementation will be sync HTTP (OkHttp,
  Retrofit's blocking `execute`, urllib in tests). Each implementer who
  forgets to switch dispatchers gets the same opaque crash — a sharp
  failure mode the library can prevent at zero cost.
- The library already enforces `Dispatchers.IO` for its own HTTP
  (post-`c03a4b1`). Treating the initiator differently is inconsistent.
- The performance cost of an unnecessary dispatcher hop (when the host
  already switched, or used an async client) is negligible.

### Arguments for #2 (host owns)

- Some hosts may want to use `Dispatchers.Default` (CPU-bound JWT
  signing), or a custom dispatcher (test scheduler, app-wide IO pool).
  Library forcing `Dispatchers.IO` precludes these.
- Honoring the suspend-fun contract literally is more idiomatic Kotlin.
  Coroutines documentation argues that suspend functions should be
  "main-safe" by their own design rather than relying on callers.
- Documenting the threading expectation in the `UploadInitiator` KDoc
  is cheap and catches the issue at code-review time.

### Recommendation (non-binding)

**Pick #1.** The asymmetric cost makes the call clear: forgetting to
switch dispatchers is a release-blocking crash; an unwanted dispatcher
hop is a microsecond. Document #1 in the `UploadInitiator` KDoc so
readers know the library's contract. Hosts that genuinely want a
non-IO dispatcher can do `withContext(MyDispatcher) { ... }` inside
their initiator and the library's outer wrap is a no-op.

## Decision (fill in when made)

> *To be decided.* When chosen, edit this section, set Status to
> `accepted`, and add Implementation notes covering: which file
> changes, what the `UploadInitiator` KDoc says, and what (if any)
> equivalent dispatch the library does for the chunk PUT path (already
> on `Dispatchers.IO` post-`c03a4b1`).

## Consequences

To be filled in when decided.

## Implementation notes

To be filled in when decided.
