# Testing

Tests live in `core/tests.py`.

## Required Local Validation

From repo root on Windows:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

For Compose/deployment validation:

```bash
docker compose run --rm migrate
docker compose up -d web packer-worker
docker compose logs --tail=100 packer-worker
```

## Current Automated Coverage Map

### Template Create API

Class: `TemplateCreateApiTests`

Covers:

- Successful template create queues a job.
- Request/status manifests are written.
- Windows admin password is redacted in request manifest.
- Same owner gets next sequential VMID.
- Missing directory profile requires sign out/sign in.
- Windows payload requires Windows fields.
- Static networking is rejected for template builds.
- Student cannot create templates under faculty-only policy.

### Template Status API

Class: `TemplateStatusApiTests`

Covers:

- Owner can see status and ISO transfer progress.
- Status payload includes build profile.
- Status payload does not expose workspace/log paths.
- Other users get `404`.

### Login Redirects

Class: `LoginRedirectTests`

Covers:

- Anonymous home redirects to login with `next`.
- JSON login returns next target.
- Authenticated GET `/login/` redirects to safe next target.
- Logout clears session and redirects to login.

### Settings View

Class: `SettingsViewTests`

Covers:

- Settings page shows read-only account data.
- Settings page shows directory profile fields.
- Settings page shows template access state.
- Fragment response includes expected account data.

### VM Start API

Class: `VmStartApiTests`

Covers:

- Login required.
- Proxmox failures return HTTP `502`.
- Provisioning from selected template returns VM payload.
- Missing template ID rejected.
- Other user's template rejected.
- Static network without gateway rejected.
- Disk smaller than source template rejected.

### Template List API

Class: `TemplateListApiTests`

Covers:

- Only current user's completed templates are returned.

### Proxmox URL Normalization

Class: `ProxmoxUrlNormalizationTests`

Covers:

- Root base URL gets `/api2/json`.
- Existing `/api2/json` is preserved.
- Worker URL builder accepts root and versioned base URLs.
- Client uses normalized API base.

### VM Provisioning Service

Class: `VmProvisioningServiceTests`

Covers:

- Successful service flow persists running VM.
- Clone failure marks VM failed.

### Active Directory Endpoint Handling

Class: `ActiveDirectoryEndpointTests`

Covers:

- IP host adds domain fallback.
- Forced port/SSL applied to all hosts.
- Explicit SSL false limits default to LDAP.
- Authentication stops retrying on invalid credentials.
- Authentication retries after connectivity failure and succeeds.
- Authentication syncs directory profile and faculty role.

### Database Settings

Class: `DatabaseSettingsTests`

Covers:

- Defaults to SQLite when `DATABASE_URL` is missing.
- Parses PostgreSQL `DATABASE_URL`.

### Static Settings

Class: `StaticSettingsTests`

Covers:

- Static root and manifest storage are configured.

### Worker Execution

Class: `WorkerExecutionTests`

Covers:

- Worker success path collects software results.
- Worker failure path writes error summary.
- Enqueue writes request/status manifests.
- Stale running jobs are recovered as failed.
- Dev bypass skips Packer/tool prereqs.
- Runtime readiness requires Packer when bypass is disabled.
- Dev bypass mode writes result files and succeeds.

### ISO Staging

Class: `IsoStagingTests`

Covers:

- ISO download writes file and manifest.
- Existing matching manifest reuses staged ISO.
- Filename conflict gets suffix.
- Preflight accepts shared storage with ISO and image content.
- Preflight accepts separate ISO-capable storage.
- Preflight accepts permission-limited storage metadata with warnings.

### Artifact Generation

Class: `ArtifactGenerationTests`

Covers:

- Ubuntu user-data avoids installer-time guest-agent late commands.
- Windows unattend BIOS disk layout.
- Windows unattend UEFI disk layout.
- Windows bootstrap installs guest agent and runs Sysprep.
- Windows UEFI HCL uses correct EFI type syntax.
- Ubuntu cloud-init ISO uses ISO storage pool.
- Windows `AUTOUNATTEND` CD uses ISO storage pool.
- Boot and driver ISOs use staged Proxmox `iso_file` references.
- Log redaction masks secret values.
- Machine-readable error summary selection.
- Log error summary includes relevant lines.
- Failure summary prefers machine-readable Packer errors.

## Manual Verification Scope

Automated tests mock external services. Before production use, manually verify:

- AD login with a valid faculty account.
- AD login with invalid credentials.
- AD login when one domain controller is unreachable and another works.
- Settings page shows expected AD role and identity fields.
- ISO inspect with a valid public/internal ISO URL.
- ISO inspect with bad URL, non-ISO URL, and unreachable URL.
- Software inspect with expected installer/package URLs.
- Template create for:
  - Ubuntu autoinstall.
  - Debian preseed.
  - Windows BIOS.
  - Windows UEFI + TPM.
- Worker queue claim after a real web-created job.
- ISO staging progress on a large ISO.
- Packer plugin download/cache behavior.
- Packer validate/build behavior against real Proxmox.
- VM provisioning from a completed template.
- VM provisioning static network validation.
- Proxmox clone/config/resize/start failure behavior.

## Current Gaps

- No browser/E2E tests for the modal wizard.
- No live Proxmox acceptance tests.
- No live AD integration tests.
- No live NAS/NFS permission test command.
- No test for deployment helper script.
- No automated test for `/etc/fstab` remount behavior.
- No tests for retry/cancel because those features are not implemented.
