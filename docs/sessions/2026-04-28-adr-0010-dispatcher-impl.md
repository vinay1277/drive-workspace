# Session: 2026-04-28 — Apply ADR-0010 (library auto-dispatches initiator)

> **Smallest possible session.** Implement the decision in
> [ADR-0010](../decisions/0010-library-dispatcher-discipline.md). One library
> file, one KDoc, one tester cleanup, one unit test. Should complete in 30–45
> minutes including build + verification.

## Goal

`DriveUploaderImpl.runUpload` invokes the host-supplied
`UploadInitiator.initiate(request)` on `Dispatchers.IO` regardless of the
collector's dispatcher. The redundant `withContext(Dispatchers.IO)` in the
tester's `BackendInitiator.initiate()` is removed. A unit test asserts the
dispatcher discipline so a future contributor cannot regress it.

## Required reading (before writing code)

- `docs/decisions/0010-library-dispatcher-discipline.md` — the full
  Implementation notes section is your spec
- `docs/architecture.md` §9 (Android API sketch) for orientation
- The Phase 1 outcome at the bottom of
  `docs/sessions/2026-04-26-phase1-skeleton.md` — the "Follow-up
  verification" section explains the bugs this ADR forecloses

Do not read prior session transcripts.

## In scope

### Library

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
  Add imports for `kotlinx.coroutines.Dispatchers` and
  `kotlinx.coroutines.withContext`.

- `android/library/src/main/kotlin/com/driveworkspace/uploader/api/UploadInitiator.kt`:
  Append a `**Threading**` paragraph to the KDoc — exact wording is in
  ADR-0010 Implementation notes.

### Tester

- `android/tester/src/main/kotlin/com/driveworkspace/tester/Initiators.kt`:
  Remove the `withContext(Dispatchers.IO)` wrap inside
  `BackendInitiator.initiate()` (introduced in commit `35202e7`). Drop
  the corresponding imports if they become unused. Update the comment
  to reference ADR-0010 instead of the bug-fix commit.

### Tests

- New file: `android/library/src/test/kotlin/com/driveworkspace/uploader/internal/DriveUploaderDispatcherTest.kt`
- Approach: a fake `UploadInitiator` whose `initiate` records
  `Thread.currentThread().name` (or
  `kotlinx.coroutines.currentCoroutineContext()[CoroutineDispatcher]`).
  Collect the resulting flow on `Dispatchers.Unconfined` (or
  `runTest` with default scheduler) so the test runs on the JVM. Assert
  the recorded dispatcher is **not** `Dispatchers.Unconfined` — i.e.
  the library forced a hop. Easiest concrete check:
  `Thread.currentThread().name.startsWith("DefaultDispatcher")` is true
  inside the recorded initiator (Kotlin's `Dispatchers.IO` runs on the
  shared default-dispatcher pool whose threads are named that way).
- Keep the test JVM-only. The full instrumentation gap (collecting on
  `Dispatchers.Main` against real Android) is captured separately in
  the Phase 3 task list.

## Out of scope

- Phase 2B work (real Drive REST calls). Blocked on operational
  provisioning per ADR-0008.
- Android instrumentation tests. Phase 3.
- Any change to `ResumableUploadEngine`. Already on `Dispatchers.IO`
  post-`c03a4b1`.
- Touching `prefetchSessions` (does not exist yet — ADR-0003 work
  lands later).

## Definition of done

- [ ] `DriveUploaderImpl.runUpload` wraps the initiator call in
  `withContext(Dispatchers.IO)`. Verified by `git diff`.
- [ ] `UploadInitiator` KDoc gains the threading paragraph.
- [ ] `BackendInitiator.initiate()` no longer has its own
  `withContext(Dispatchers.IO)` wrap; comment now points at ADR-0010.
- [ ] New test in `DriveUploaderDispatcherTest.kt` passes:
  `./gradlew :library:testDebugUnitTest`.
- [ ] All existing tests still pass (no regression):
  `./gradlew :library:test :tester:assembleDebug`.
- [ ] `docs/plan.md` "Open work outside the phase plan" — the
  ADR-0010 application bullet is removed (it's now done).
- [ ] One commit, message references this session brief filename.

## Notes / open questions

1. **Test framework choice**: the existing library tests use plain
   JUnit + MockWebServer + Robolectric (for Room). The dispatcher test
   needs neither HTTP nor Room — plain JUnit + `kotlinx.coroutines.test`
   (`runTest`) is sufficient. `kotlinx-coroutines-test` is already a
   `testImplementation` dep; verify before adding.
2. **Should `DriveUploaderDispatcherTest` also assert the engine's chunk
   PUT runs on IO?** Strictly out of scope for this ADR (chunk PUT
   dispatch is ADR-0010-adjacent but already handled by `c03a4b1`); add
   a one-line FIXME comment in the new test pointing at a future
   instrumentation test instead.
3. **Will the library auto-dispatch break any existing test?** Possibly
   — `ResumableUploadEngineTest` runs on the JVM and uses MockWebServer.
   The test should be unaffected because it's testing the engine, not
   the impl. Confirm by running the full suite.

## Outcome

Landed as specified, single commit, on 2026-04-26.

- `DriveUploaderImpl.runUpload` now wraps `initiator.initiate(request)` in
  `withContext(Dispatchers.IO) { ... }`. Imports added for
  `kotlinx.coroutines.Dispatchers` and `kotlinx.coroutines.withContext`.
- `UploadInitiator` KDoc gains the **Threading** paragraph (verbatim from
  ADR-0010).
- `BackendInitiator.initiate()` no longer carries its own
  `withContext(Dispatchers.IO)` wrap; the now-unused
  `kotlinx.coroutines.Dispatchers` / `withContext` imports are dropped, and
  the body comment now references ADR-0010 instead of the bug-fix commit.
- New unit test
  `android/library/src/test/kotlin/com/driveworkspace/uploader/internal/DriveUploaderDispatcherTest.kt`
  uses a fake `UploadInitiator` that records `Thread.currentThread().name`
  and then throws to short-circuit the engine. The test collects the flow
  via `runTest` (so the test scheduler — not IO — owns the flow body) and
  asserts the recorded thread name starts with `"DefaultDispatcher-worker"`,
  proving the library forced the IO hop. Includes a FIXME pointing at the
  Phase 3 instrumentation test.

Verification:

- `./gradlew :library:testDebugUnitTest --tests
  com.driveworkspace.uploader.internal.DriveUploaderDispatcherTest` →
  passes.
- `./gradlew :library:test :tester:assembleDebug` → BUILD SUCCESSFUL; no
  pre-existing tests regressed (`ResumableUploadEngineTest`,
  `RetryPolicyTest`, `LocalCheckpointStoreTest` all still green) and the
  tester app still builds clean after the import cleanup.

Open-question resolution from the brief:

1. `kotlinx-coroutines-test` was already a `testImplementation` dep in
   `android/library/build.gradle.kts` — no dep change needed.
2. The chunk-PUT dispatcher assertion was deliberately *not* added; only a
   one-line FIXME points to a Phase 3 instrumentation test, per the brief.
3. No existing test was disturbed by the auto-dispatch — the engine tests
   are scoped to `ResumableUploadEngine`, which already runs its own
   `runInterruptible(Dispatchers.IO)`.

Plan delta: the ADR-0010 application bullet is removed from
`docs/plan.md` "Open work outside the phase plan"; the Phase 3
instrumentation-test bullet remains.
