# ADR-0010: Library dispatcher discipline for host-supplied callbacks

- **Status**: accepted
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

This ADR captures the question of how the library should treat the
*host-supplied* `UploadInitiator.initiate()` call.

## Decision

**The library auto-dispatches `UploadInitiator.initiate()` to
`Dispatchers.IO`.** Specifically: `DriveUploaderImpl.runUpload` wraps the
`initiator.initiate(request)` call in `withContext(Dispatchers.IO)`.

The asymmetric cost makes the call clear: forgetting to switch
dispatchers is a release-blocking crash; an unwanted dispatcher hop is a
microsecond. Hosts that genuinely want a non-IO dispatcher can do
`withContext(MyDispatcher) { ... }` inside their initiator — the
library's outer wrap is a no-op in that case.

This matches the library's existing posture for chunk PUTs: post-c03a4b1,
`ResumableUploadEngine.executeAsync` uses
`runInterruptible(Dispatchers.IO) { ... }`. Auto-dispatching the
initiator extends the same defensive policy to the host plug point.

## Consequences

**Positive**:
- Future host `UploadInitiator` implementations cannot crash with
  `NetworkOnMainThreadException` on a sync HTTP call. The most common
  failure mode (OkHttp/Retrofit blocking `execute`) is foreclosed.
- The library's threading contract is uniform: all blocking work the
  library invokes — its own and host-supplied — runs on
  `Dispatchers.IO`.
- The tester app's `BackendInitiator.initiate()` no longer needs its
  defensive `withContext(Dispatchers.IO)` wrap. Sample code is simpler.

**Negative**:
- A host that wants the initiator on `Dispatchers.Default` or a custom
  dispatcher pays the cost of a no-op `withContext(IO)` hop before its
  own `withContext` reverses it. Negligible — a few microseconds — and
  outweighed by the crash-prevention property.
- The library's behavior diverges slightly from a literal reading of
  Kotlin coroutines' "main-safe" idiom (where a `suspend fun` is
  expected to handle its own dispatching). We document this divergence
  explicitly in the `UploadInitiator` KDoc so callers are not surprised.

**Rejected alternative**:
- *Host owns the dispatcher (option 2 in the original Decision section)*:
  more idiomatic Kotlin, but every implementer would re-discover the
  Phase 1 bug. The expected reader of `UploadInitiator` is a host
  application engineer who may not be a coroutines expert; the library
  protects them.

## Implementation notes

A future session executes this change. Scope (~15 lines of code, plus
tests):

### Library changes

- `android/library/src/main/kotlin/com/driveworkspace/uploader/internal/DriveUploaderImpl.kt`:
  In `runUpload`, replace
  ```kotlin
  val session = try {
      initiator.initiate(request)
  } catch (t: Throwable) { ... }
  ```
  with
  ```kotlin
  val session = try {
      withContext(Dispatchers.IO) { initiator.initiate(request) }
  } catch (t: Throwable) { ... }
  ```
  Add the imports for `kotlinx.coroutines.Dispatchers` and
  `kotlinx.coroutines.withContext`.

- `android/library/src/main/kotlin/com/driveworkspace/uploader/api/UploadInitiator.kt`:
  Add to the KDoc:
  > **Threading**: the library invokes this method from
  > `Dispatchers.IO`. Implementations may safely call blocking I/O
  > directly (e.g. synchronous OkHttp). If the implementation needs a
  > different dispatcher (e.g. `Dispatchers.Default` for CPU-bound
  > work), use `withContext` inside the implementation; the library's
  > outer dispatch becomes a no-op.

### Tester cleanup (optional but recommended)

- `android/tester/src/main/kotlin/com/driveworkspace/tester/Initiators.kt`:
  Remove the explicit `withContext(Dispatchers.IO)` wrap inside
  `BackendInitiator.initiate()` (commit `35202e7`). The library's outer
  dispatch makes it redundant. Update the comment to reference this
  ADR rather than the bug-fix commit.

### Tests

- A unit test that asserts `DriveUploaderImpl` invokes the initiator on
  a non-Main dispatcher. Easiest implementation: a test
  `UploadInitiator` that records `Thread.currentThread().name` (or
  checks `kotlinx.coroutines.currentCoroutineContext()[CoroutineDispatcher]`)
  and assert it is not `Dispatchers.Main`.
- An instrumentation test on Android (Phase 3) that exercises the full
  upload path collected on `Dispatchers.Main`. This is the gap the Phase
  1 outcome already flagged: the JVM-only unit tests passed because the
  JVM has no main-thread network enforcement. Track this as a Phase 3
  task separately from this ADR.

### Out of scope for this ADR

- Whether the library should also auto-dispatch the chunk PUT path.
  Already handled by commit `c03a4b1`
  (`runInterruptible(Dispatchers.IO)`).
- Whether `prefetchSessions` (when added per ADR-0003) should also
  auto-dispatch. Yes — same reasoning. The session implementing
  prefetch follows this ADR's pattern.
