# Troubleshooting

> **Living document.** Captures concrete failures we've hit and the fixes
> that worked. Add entries when you discover a new gotcha; don't delete
> entries even after they're rare — the next person searching will find
> them faster than re-deriving the cause.

> **How to use this doc**: Cmd/Ctrl-F for the error string or the
> behaviour you're seeing. Each entry is self-contained.

---

## Table of contents

- [Service-account & authentication issues](#service-account--authentication-issues)
- [Drive API quirks (Shared Drives, quota, scope)](#drive-api-quirks-shared-drives-quota-scope)
- [Workspace setup (Cloud Identity vs Workspace, admin console)](#workspace-setup-cloud-identity-vs-workspace-admin-console)
- [DNS / domain verification](#dns--domain-verification)
- [Android library threading & dispatchers](#android-library-threading--dispatchers)
- [Build / dev environment](#build--dev-environment)
- [Multiple Google accounts in one Chrome profile](#multiple-google-accounts-in-one-chrome-profile)
- [Library specifics](#library-specifics)

---

## Service-account & authentication issues

### `403 storageQuotaExceeded` when SA creates a file

**Symptom**:

```
googleapiclient.errors.HttpError: <HttpError 403 ...
returned "The user's Drive storage quota has been exceeded.">
```

…even when `parents=[<user-owned-folder-id>]` is set.

**Cause**: Service accounts have **zero personal Drive quota**. When an
SA creates a file via `drive.files.create()`, Google charges the
storage to the SA itself, not the parent folder's owner. SA's quota is
zero → instant 403.

This affects: spreadsheet creation, file uploads, any `files.create`
with non-folder mime type. Folder creation works because folders are
metadata-only (no quota).

**Fix**: Host all `drive_workspace` content inside a **Shared Drive**.
Files in Shared Drives charge to the org's pooled storage, not any SA.

Per [ADR-0011](decisions/0011-sa-storage-quota.md):
1. Workspace plan must be Business Standard+ (Starter has no Shared
   Drives).
2. Create a Shared Drive in the org.
3. Add the SA as **Content Manager** on that drive.
4. All Drive API calls pass `supportsAllDrives=True`,
   `includeItemsFromAllDrives=True`, `corpora="drive"`,
   `driveId=<shared_drive_id>`.

Reference: [`backend/.secrets/bootstrap_test_workspace.py`](../backend/.secrets/bootstrap_test_workspace.py)
demonstrates the correct flow. Path B 2.0 in
[`docs/deployment.md`](deployment.md) is the live setup.

---

### SA email gets external-share warning when added to a Shared Drive

**Symptom**: When sharing a Shared Drive (or any folder) with the SA
email, Google shows:

> "<sa-email> is external to <Workspace name>, who owns the item. This
> organization encourages caution when sharing externally."

**Cause**: The SA lives in a different GCP project than the Workspace
that owns the Shared Drive. From the Workspace's perspective, the SA
is an "external" user.

**Fix**: This is expected and explicitly anticipated by ADR-0011's
implementation note: *"Shared Drive external-sharing policy must allow
non-org members."* Click **Share anyway**.

If your Workspace admin has restricted external sharing org-wide, you
may need to enable it in admin.google.com → Apps → Google Workspace →
Drive and Docs → Sharing settings → "Sharing options" → "Sharing
outside of \<org\>" → ON.

---

### Service-account JSON file not found

**Symptom**:

```
FileNotFoundError: Service-account key file not found: /path/to/sa.json
```

**Cause**: `FileAuthenticator` resolves the path at construction time
(fail-fast). The path you passed doesn't exist or has a typo.

**Fix**: Confirm the file is at `backend/.secrets/dev-sa.json` (the
canonical local-dev path). Note `.secrets/` is gitignored, so a fresh
clone won't have it — the first developer to clone needs to copy the
JSON from a secure location (or generate a new SA key). See
[`docs/deployment.md`](deployment.md) for the local secret path
convention.

---

## Drive API quirks (Shared Drives, quota, scope)

### Files in Shared Drive don't appear in `files.list` results

**Symptom**: SA can see the Shared Drive in `drive.drives().list()`, but
`drive.files().list(q="'<folder_id>' in parents")` returns empty even
though the folder has children.

**Cause**: By default, the v3 Drive API hides Shared Drive content
unless you explicitly opt in.

**Fix**: Pass these flags on **every** `files.list` and `files.get`:

```python
drive.files().list(
    q=...,
    fields=...,
    supportsAllDrives=True,
    includeItemsFromAllDrives=True,
    corpora="drive",
    driveId=SHARED_DRIVE_ID,
).execute()
```

`corpora="drive"` + `driveId=...` constrains the search to that one
Shared Drive (faster than `corpora="allDrives"`). Per ADR-0011.

---

### `Sheets API spreadsheets.create` 403s with "caller does not have permission"

**Symptom**:

```
HttpError: <HttpError 403 ...
returned "The caller does not have permission">
```

…on `sheets.spreadsheets().create()`.

**Cause**: Same root cause as the Drive 403 above. Sheets API's
`create` ultimately makes a Drive `files.create` under the hood,
which charges to SA's quota.

**Fix**: Don't use `sheets.spreadsheets().create()` from an SA. Instead:

1. Create the spreadsheet via Drive API:
   ```python
   drive.files().create(
       body={"name": "log", "mimeType": "application/vnd.google-apps.spreadsheet",
             "parents": [<folder_in_shared_drive>]},
       fields="id",
       supportsAllDrives=True,
   ).execute()
   ```
2. Then use Sheets API for content (`values.append`, `values.update`).
   Sheets API content operations don't allocate new files, so they
   don't hit the quota wall.

---

## Workspace setup (Cloud Identity vs Workspace, admin console)

### `admin.google.com` rejects you with "Sign in with an administrator account"

**Symptom**: After signing in to admin.google.com, Google shows:

> "Sign in with an administrator account. To sign in to admin.google.com,
> use an administrator account for a managed Google service, such as
> Google Workspace or Cloud Identity."

**Cause**: Two possibilities:

1. The account isn't an admin of any managed service. Personal Gmail
   accounts (`@gmail.com`) without an associated Workspace fall here.
2. There IS a managed service (Cloud Identity Free, auto-created when
   you signed up for Google Cloud) but it has no admin role assigned
   to your user.

Critically: a Cloud Identity Free org appears in GCP project pickers
as if it were a Workspace, but it doesn't include the Workspace admin
console. Shared Drives, the Drive sharing-settings toggle, and most
admin features are unavailable until Workspace is subscribed.

**Fix**: Subscribe to Google Workspace Business Standard or higher.
Business Starter doesn't include Shared Drives. After subscribing,
admin console becomes available; sign in with the Workspace admin
user (typically `<username>@<your-domain>`, not your personal Gmail).

The signup wizard at <https://workspace.google.com/business/signup/welcome>
detects existing Cloud Identity orgs and offers a smooth upgrade.

---

### "Members can create shared drives" toggle is OFF by default

**Symptom**: In Drive web UI on the Shared Drives page, clicking "+ New"
does nothing. Or shows the empty state "When you're added to one, it
will show up here" forever.

**Cause**: New Workspace tenants ship with shared-drive-creation
**prevented** by default. Even Workspace admin users can't create
Shared Drives until the toggle is flipped.

**Fix**: admin.google.com → Apps → Google Workspace → Drive and Docs →
Sharing settings → **Shared drive creation** → ensure
**"Prevent users in `<org>` from creating new shared drives"** is set
to **OFF** (i.e. NOT preventing). Save. Wait 1-2 minutes for
propagation; then "+ New" → "Create a shared drive" works.

---

## DNS / domain verification

### Workspace verification screen accidentally closed

**Symptom**: Closed the browser tab during Workspace signup at the TXT
verification step, before clicking Verify.

**Recovery**:

1. Check the email account that started the signup (often a personal
   Gmail). Google sends a "Welcome to Google Workspace" email with a
   "Finish setup" link. **That link is the resume URL.**
2. If no email arrived: navigate to admin.google.com, sign in as the
   Workspace admin user (`<admin>@<your-domain>`). The setup wizard
   resumes from where it left off.
3. The TXT verification value you copied is still valid; just paste it
   into your DNS provider's TXT record and click Verify in the wizard.

If you didn't copy the value: the wizard re-issues it. Don't worry.

---

### TXT vs MX records — which does Workspace verification need?

**Common confusion**: Workspace setup asks two distinct things:

1. **Domain ownership verification** → TXT record (`google-site-verification=...`)
2. **Email delivery routing** → MX records (point to Google's mail
   servers, e.g. via Namecheap's "Gmail" mail-settings preset)

Adding only the MX records does **not** satisfy ownership verification.
You need the TXT record explicitly.

**Order**: do them in either order; both safe. If you don't currently
use email at the domain, enabling Gmail MX records is fine and gives
you `<admin>@<your-domain>` Workspace mailboxes.

If you DO currently have email at the domain (other mail server,
forwarder, etc.), the Gmail MX preset replaces existing MX. Your
existing email-receiving stops. Be deliberate.

---

### TXT record added but verification still fails

**Symptom**: Added the `google-site-verification=...` TXT record at
your DNS provider; clicking Verify in the Workspace wizard says "We
couldn't verify your domain."

**Causes (in order of likelihood)**:

1. **DNS propagation delay**. Wait 5-30 minutes; rare cases up to 2
   hours. Use <https://dnschecker.org> to confirm the TXT record is
   visible at multiple resolvers before clicking Verify again.
2. **Wrong host**. The TXT record's "Host" field should be `@`
   (the apex / root). If you put it on a subdomain, verification fails.
3. **Value with stray whitespace or smart quotes**. Some DNS UIs auto-
   correct quotes. The value should start with `google-site-verification=`
   and end with the alphanumeric/underscore string — no leading/trailing
   spaces.
4. **Multiple TXT records on `@`**. Multiple TXT records is fine and
   common (SPF, DKIM, etc. coexist), but make sure your `google-site-
   verification` line is its own record, not concatenated to another.

---

## Android library threading & dispatchers

### `NetworkOnMainThreadException` from `UploadInitiator.initiate`

**Symptom**: Tester app crashes (or shows "Failed: InitiateFailed") when
clicking Upload. Logcat shows:

```
android.os.NetworkOnMainThreadException
  at okhttp3.Dns$Companion$DnsSystem.lookup(Dns.kt:49)
  at ... BackendInitiator.initiate
```

**Cause**: A custom `UploadInitiator` implementation called sync OkHttp
from `Dispatchers.Main`. This *was* a real bug in the Phase 1 tester;
it was caught by the S4 instrumentation test.

**Fix in modern library (post-`65fb192`)**: This shouldn't happen.
`DriveUploaderImpl.runUpload` wraps `initiator.initiate(request)` in
`withContext(Dispatchers.IO)` per ADR-0010. If you still see this,
update to the latest library.

**If you're on an older library**: temporarily wrap your initiator's
body in `withContext(Dispatchers.IO)` yourself:

```kotlin
override suspend fun initiate(request: UploadRequest): UploadSession =
    withContext(Dispatchers.IO) {
        // your sync HTTP code
    }
```

Then upgrade.

Reference: [ADR-0010](decisions/0010-library-dispatcher-discipline.md).

---

### `StrictMode ThreadPolicy violation` in `ResumableUploadEngine`

**Symptom**: Upload starts, library catches `NetworkOnMainThreadException`
on initiate (handled), but then chunk PUT response handling crashes
with a StrictMode violation in `extractWebViewLink` or the implicit
`Response.close()` path.

**Cause**: Library bug pre-`43f3611` — `executeAsync` switched to IO
for OkHttp's `execute()` but the `.use { resp -> classifyChunkResponse(resp) }`
block resumed on the caller's dispatcher (Main).

**Fix**: Update the library to `43f3611` or later. ADR-0010 sibling-fix
note covers this.

---

### Sync flow runs on Dispatchers.Main but the library doesn't crash on JVM tests

**Cause**: The JVM doesn't enforce main-thread network policy. The
library's JVM-only unit tests are silent on this class of bug.

**Fix**: Phase 3 has an Android instrumentation test
(`MainDispatcherInstrumentationTest`) that runs against real Android
and catches this. Run it before shipping changes that touch
`DriveUploaderImpl`, `ResumableUploadEngine`, or the dispatch path:

```bash
cd android && ./gradlew :library:connectedDebugAndroidTest
```

Requires a connected emulator or device.

---

## Build / dev environment

### `winget install Docker.DockerDesktop` fails with exit code 4294967291

**Symptom**:

```
Installer failed with exit code: 4294967291
```

**Cause**: Exit code 4294967291 = unsigned representation of -5 =
`ERROR_ACCESS_DENIED`. Almost always means winget didn't get the UAC
elevation it needed even when run from an admin PowerShell. Sometimes
WSL2 missing or antivirus blocking.

**Fix**: Download the Docker Desktop installer directly from
<https://www.docker.com/products/docker-desktop/>. Right-click the
`.exe` → "Run as administrator". This gives you real UI feedback if
WSL2/Hyper-V/AV is the actual blocker.

Workaround if you don't strictly need Docker: the reference Flask
server runs fine via `flask run` directly:

```powershell
cd D:\drive-workspace\backend
.\.venv\Scripts\Activate.ps1
$env:FLASK_APP = "reference_server.app"
flask run --host=0.0.0.0 --port=8080
```

Postgres in `docker-compose.yml` is for Phase 2's
`SqlAlchemyPrincipalStore`; Phase 1 reference server doesn't use it.

---

### PowerShell shows `NativeCommandError` after curl/flask runs

**Symptom**: PowerShell wraps native command stderr as
`RemoteException`, looks like an error even when the command succeeded.

**Fix**: Ignore the wrapping, look at the actual stdout. For curl,
add `-s` (silent) to suppress the progress meter that PowerShell
mistakes for stderr:

```powershell
curl.exe -s http://localhost:8080/health
```

For flask: the "WARNING: This is a development server" message is
stderr too; flask is running fine.

---

### `adb` not on PATH

**Symptom**:

```
adb : The term 'adb' is not recognized as the name of a cmdlet...
```

**Cause**: Android SDK platform-tools directory not in PATH.

**Fix** (Windows, session-only):

```powershell
Get-ChildItem -Path $env:LOCALAPPDATA\Android, "C:\Android",
    "C:\Program Files\Android", "C:\Program Files (x86)\Android"
    -Filter adb.exe -Recurse -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
# Copy the path that prints, then:
Set-Alias adb '<that-path>'
```

For permanent PATH addition, use Windows Settings → Environment
Variables → User PATH → add `<sdk>\platform-tools`.

---

## Multiple Google accounts in one Chrome profile

### Wrong account at admin.google.com / Drive / GCP

**Symptom**: You signed in as the right account but Google's dashboard
shows the wrong tenant or "no admin access."

**Cause**: Chrome can have multiple Google accounts in one profile.
Google numbers them: `authuser=0` is the primary, `authuser=1` second,
`authuser=2` third, etc. URLs default to authuser=0; if your admin
account is account #2, you need to switch.

**Fix**: Append `?authuser=N` (or `&authuser=N` if the URL has other
params) where N is the index of the account you want:

```
https://admin.google.com/?authuser=1
https://drive.google.com/drive/u/2/shared-drives
https://console.cloud.google.com/...?authuser=1
```

For Drive specifically, the URL form is `/drive/u/<N>/...`.

To find which N corresponds to which account: open
<https://accounts.google.com>, count the accounts in order. Or open
each account's URL and check the avatar in the top-right.

---

## Library specifics

### Prefetch bank fingerprint mismatch — bank hits don't happen

**Symptom**: Tester app prefetched N sessions but `upload(...)` still
calls `initiator.initiate` (live), bypassing the bank.

**Cause**: The session prefetch bank matches by
`(mimeType, kindHint, fileSizeBracket)`. If the upload's `UploadRequest`
has a different fingerprint than what was prefetched, no match.

**Fix**: When prefetching, use a `requestTemplate` whose mime/kind/size
will match real uploads. The size bracket is one of `[<1MB, 1-10MB,
10-50MB, 50MB+]` — prefetch sessions in the bracket your real files
will fall into.

If you can't predict ahead, prefetch a few sessions in each likely
bracket. Or accept that bank misses fall through to live initiate
(safe, just costs the round-trip).

Reference: [ADR-0003](decisions/0003-session-prefetch-bank.md).

---

### `Room.databaseBuilder` migration error after upgrading library

**Symptom**: After updating to a library version that bumped the Room
schema (e.g. v1 → v2 for the prefetch bank table), the host app
crashes at startup with a Room migration error.

**Cause**: Pre-v0.1.0 the library ships destructive migrations. Each
schema bump drops and recreates the library's local DB.

**Fix**: This is by design until v1.0. Wipe the host app's data on
upgrade (`adb shell pm clear <package>` or uninstall + reinstall).
At v1.0+ proper migrations will be authored.

---

## Adding new entries

When you hit a new failure that takes more than 15 minutes to diagnose:

1. Add an entry under the right category (or create a new category).
2. Format: **Symptom** → **Cause** → **Fix** → **Reference** (commit/ADR/code).
3. Cross-link any relevant ADR or session brief.
4. Commit with message `docs(troubleshooting): add <short summary>`.
