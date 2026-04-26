# Session: 2026-05-01 — Phase 3 instrumentation test (ADR-0010 seed)

> **Test-only session.** Add an Android instrumentation test that
> exercises the full upload path with the Flow collected on
> `Dispatchers.Main` against a real Android runtime. The JVM-only unit
> tests in the library passed throughout Phase 1 even though both
> main-thread-network bugs (commits `35202e7` and `c03a4b1`) were
> live — because the JVM has no main-thread enforcement. This session
> fills that gap.

## Goal

By end of session: `./gradlew :library:connectedDebugAndroidTest`
runs a new instrumentation test that:

- Stands up a `MockWebServer` inside the test process.
- Constructs `DriveUploaderImpl` with a fake `UploadInitiator` whose
  `initiate` does sync OkHttp.
- Collects the resulting Flow on `Dispatchers.Main` (the actual Android
  Main looper, not a test scheduler).
- Asserts the upload completes Successfully without throwing
  `NetworkOnMainThreadException`.
- Asserts the initiator's HTTP call did NOT actually run on Main (proves
  the library's `withContext(Dispatchers.IO)` wrap holds).

## Required reading (before writing code)

- `docs/decisions/0010-library-dispatcher-discipline.md` — the spec
  this test enforces
- `docs/sessions/2026-04-26-phase1-skeleton.md` "Follow-up
  verification" — the bugs this test would have caught
- `docs/sessions/2026-04-28-adr-0010-dispatcher-impl.md` — the
  existing JVM unit test (`DriveUploaderDispatcherTest`) and what it
  doesn't cover
- `android/library/src/test/kotlin/com/driveworkspace/uploader/internal/DriveUploaderDispatcherTest.kt`
  — the JVM analogue
- `android/library/src/test/kotlin/com/driveworkspace/uploader/internal/ResumableUploadEngineTest.kt`
  — for the MockWebServer pattern

Do not read prior session transcripts.

## In scope

- New file: `android/library/src/androidTest/kotlin/com/driveworkspace/uploader/MainDispatcherInstrumentationTest.kt`
- The library's `build.gradle.kts` likely already declares the
  `androidTest` source set; verify before adding.
- Test uses `androidx.test.ext:junit` (already a dep), `MockWebServer`
  (test-only), and `kotlinx-coroutines-android` (already a dep).
- Test scenario (one method, no parameterization needed for first cut):
  - MockWebServer enqueues: 200 to initiate (returns a fake session URL
    that points at the same MockWebServer), then a chunked-PUT happy
    path of 308 + 200.
  - A fake `UploadInitiator` implementation does sync OkHttp inside
    `initiate`. NO `withContext(Dispatchers.IO)`. Records
    `Thread.currentThread().name` at call time.
  - Main-thread collector: `runBlocking(Dispatchers.Main) {
    uploader.upload(...).collect { ... } }`.
  - Assert: terminal `UploadProgress.Succeeded` was emitted; recorded
    initiator thread name does NOT start with "main".

## Out of scope

- Adding instrumentation tests for any other path (chunk PUT, prefetch,
  etc.). One canonical main-thread test is enough seed; expand later.
- Running on CI. The test runs locally on a connected emulator/device;
  CI integration is a separate Phase 3 task.
- Coverage tooling (jacoco etc.). Phase 3 separately.
- Modifying the production library code. If the test fails because the
  library's auto-dispatch is wrong, FIX the library — but do not
  preemptively refactor.

## Definition of done

- [ ] `./gradlew :library:connectedDebugAndroidTest` passes against a
      running emulator (or a connected device with USB debugging).
- [ ] The new test file exists at the path above and is the only
      file added by this session (plus any minimum gradle/manifest
      additions needed to make `androidTest` work).
- [ ] Test fails (deliberately revertable) when ADR-0010's auto-dispatch
      wrap is removed from `DriveUploaderImpl.runUpload`. Verify by
      temporarily reverting commit `65fb192`'s
      `withContext(Dispatchers.IO)`, re-running, observing failure,
      restoring. Don't commit the revert.
- [ ] One commit. Message references this brief filename.

## Notes / open questions

1. **Connected device required** — instrumentation tests need a real
   Android runtime. Document in the session Outcome that the runner
   must have an emulator booted or a device plugged in.
2. **`runBlocking(Dispatchers.Main)`** vs. `runOnUiThread` —
   recommend `runBlocking` because we want to collect a Flow that
   suspends; `runOnUiThread` posts a Runnable and returns. The point
   is to actually be on Main while collecting.
3. **MockWebServer URL inside the device** — the server runs in the
   test process. URLs use `server.url("/")` as base. Same pattern as
   existing JVM tests; verify it works in instrumentation context.

## Outcome

> Filled in at end of session.

(blank — to be completed)
