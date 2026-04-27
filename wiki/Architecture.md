# Architecture

## Overview

Capstone is a Django 6 monolith for creating reusable lab VM templates and provisioning student/user VMs on Proxmox. The application is intentionally simple in process boundaries:

- `web`: Django HTTP process serving pages, JSON APIs, static files, and queueing template jobs.
- `packer-worker`: Django management command process that consumes queued template jobs and runs Packer.
- Database: SQLite in local development unless `DATABASE_URL` is set; PostgreSQL in Compose/deployment.
- Shared filesystem: per-job workspaces and NAS-staged installer media.
- External systems: Active Directory, Proxmox, NAS/NFS, remote ISO/software URLs.

The web process and worker share the same Django codebase and database. The database is the source of truth for job ownership, status, payloads, and result summaries. The filesystem is used for generated build inputs, logs, staged ISO manifests, and archived job bundles.

## Runtime Components

### Django Project

- Project package: `capstoneDev`
- App package: `core`
- URL router: `capstoneDev/urls.py`
- Settings: `capstoneDev/settings.py`
- Main models: `core/models.py`
- Main views/API handlers: `core/views.py`
- AD auth backend: `core/auth_backends.py`
- Proxmox API client/service layer: `core/proxmox/client.py`, `core/proxmox/services.py`
- Template build engine: `core/template_builds.py`
- Worker command: `core/management/commands/run_template_build_worker.py`

### Frontend

- Server-rendered templates live under `templates/`.
- Page JavaScript lives under `static/js/`.
- CSS lives under `static/css/`.
- No JS framework is used.
- Partial navigation is implemented by requesting server-rendered pages with `X-Requested-With: fetch` or `prefetch`, extracting `#app-content`, page-specific head links, and page-specific scripts.

### Docker and Deployment

- `Dockerfile` has `web-runtime` and `packer-runtime` targets.
- `web-runtime` runs Gunicorn by default.
- `packer-runtime` installs Packer 1.11.2 plus `curl`, `jq`, `unzip`, and `xorriso`.
- `compose.yaml` defines `migrate`, `web`, and `packer-worker`.
- `compose.dev.yaml` adds source bind mounts and local development defaults.
- `docker-entrypoint.sh` waits for PostgreSQL, optionally runs migrations, optionally runs `collectstatic`, then execs the service command.
- `docker/packer-worker/start.sh` prepares worker directories and runs `manage.py run_template_build_worker`.
- `scripts/deploy.sh` is the deployment helper for the host VM.

## Authentication Flow

1. User submits JSON credentials to `POST /login/` with `X-Requested-With: fetch`.
2. `login_view()` calls Django `authenticate()`.
3. `ActiveDirectoryBackend` reads:
   - `AD_LDAP_HOST`
   - `AD_LDAP_PORT`
   - `AD_LDAP_USE_SSL`
   - `AD_LDAP_CONNECT_TIMEOUT`
   - `AD_UPN_SUFFIX`
   - `AD_BASE_DN`
4. The backend builds candidate LDAP endpoints.
5. If `AD_LDAP_HOST` is a single IP and `AD_UPN_SUFFIX` is available, the AD domain is tried as a fallback endpoint.
6. Multiple configured hosts can be separated by commas or semicolons.
7. DNS names are resolved to candidate IPs.
8. The last successful endpoint is cached in process memory and tried first on later logins.
9. LDAP SIMPLE bind is attempted as `username@AD_UPN_SUFFIX`.
10. On successful bind, selected AD attributes are queried by `sAMAccountName`.
11. The local Django user is created or updated.
12. A `DirectoryProfile` is updated when AD `objectSid` and RID are available.
13. `user.is_staff` is set when the inferred directory role is `faculty`.
14. Django session login is established.

Current directory role inference:

- `OU=Faculty` in the distinguished name means faculty.
- `OU=Students` in the distinguished name means student.
- Membership in built-in privileged groups such as Domain Admins also maps to faculty.
- Membership in a group containing `CN=Students` maps to student.
- Otherwise the role is `unknown`.

Production policy says AD auth is mandatory. The settings still include Django `ModelBackend` after the AD backend, which is useful for local/test flows but should be reviewed before strict production enforcement.

## Authorization

- All interactive app pages except `/login/` require authentication.
- VM provisioning requires authentication and a completed template owned by the caller.
- Template creation is controlled by `TEMPLATE_CREATION_POLICY`.
- Supported policy values:
  - `faculty_only`
  - `allow_all`
- Current settings default is `faculty_only`.
- When `faculty_only`, the code currently checks `user.is_staff`.
- `user.is_staff` is set by AD sync when role inference returns faculty.

## Template VMID Policy

Current implementation:

- `create_template_definition()` calls `_template_vmid_for_user()`.
- `_template_vmid_for_user()` requires `request.user.directory_profile.ad_rid`.
- The AD RID is used as a text prefix.
- Existing template VMIDs for that owner with the same prefix are scanned.
- The next VMID is `<ad_rid><three_digit_sequence>`.
- Example: RID `1536` creates `1536001`, then `1536002`.

This differs from the older written policy of `"100" + faculty user id`. The code behavior is what currently runs.

## Template Build Profiles

Defined in `core/packer_profiles.py`:

- `ubuntu_autoinstall`
  - target OS: `linux`
  - Packer template: `core/packer/templates/ubuntu_autoinstall.pkr.hcl`
  - Generated inputs: `user-data`, `meta-data`, Linux bootstrap script
  - Communicator: SSH
- `debian_preseed`
  - target OS: `linux`
  - Packer template: `core/packer/templates/debian_preseed.pkr.hcl`
  - Generated inputs: `preseed.cfg`, Linux bootstrap script
  - Communicator: SSH
- `windows_unattend`
  - target OS: `windows`
  - Packer template depends on firmware:
    - `windows_unattend_bios.pkr.hcl`
    - `windows_unattend_uefi.pkr.hcl`
  - Generated inputs: `Autounattend.xml`, PowerShell bootstrap script
  - Communicator: WinRM

Windows firmware options:

- `bios_legacy`
- `uefi_tpm`

Windows image selector options:

- `image_name`
- `image_index`

## Template Creation Request Flow

1. The user opens the Create VM modal and moves to Create Template.
2. The browser loads saved ISO and software history from:
   - `GET /api/iso/saved/`
   - `GET /api/software/saved/`
3. The user selects a build profile and validates an ISO URL.
4. `GET /api/iso/inspect` performs HTTP HEAD plus fallback range GET metadata inspection.
5. Step 2 software entries are normalized with `POST /api/template/validate-software/`.
6. The final Create Template action posts to `POST /api/template/create/`.
7. The backend validates:
   - build profile
   - target OS/profile match
   - template name
   - ISO URL
   - software selections
   - hardware bounds
   - DHCP-only template networking
   - Windows-specific fields when needed
8. A `TemplateDefinition` row is created.
9. A `TemplateBuildJob` row is created with status `queued` and stage `queued`.
10. The job workspace is created under `TEMPLATE_BUILD_WORKDIR/job-<uuid>/`.
11. `request.json` and `status.json` are written immediately.
12. The response returns HTTP `202` with template and job metadata.
13. The frontend enters the Build Progress step and polls `GET /api/template/builds/<uuid>/status/`.

## Worker Lifecycle

The worker command is `manage.py run_template_build_worker`.

Startup:

1. Read settings.
2. Run `ensure_worker_runtime_ready()`.
3. Create `TEMPLATE_BUILD_WORKDIR` and `PACKER_CACHE_DIR`.
4. Unless `TEMPLATE_BUILD_DEV_BYPASS=1`, verify that Packer and an ISO authoring tool are available.
5. Mark stale running jobs as failed using `recover_stale_running_jobs()`.
6. Start polling for queued jobs.

Queue claim:

1. `claim_next_queued_job()` opens a transaction.
2. It selects the oldest queued job with `select_for_update(skip_locked=True)`.
3. It marks the job `running/preflight`, sets `started_at`, and sets `last_heartbeat_at`.
4. It rewrites `status.json`.

Execution:

1. Resolve and copy the Packer HCL template into `generated/template.pkr.hcl`.
2. Run preflight checks.
3. Stage required ISOs.
4. Generate profile-specific artifacts.
5. Generate bootstrap script.
6. Generate `template.auto.pkrvars.json`.
7. Run `packer init`.
8. Run `packer validate`.
9. Run `packer build -machine-readable -color=false`.
10. Parse machine-readable output and Capstone markers.
11. Write result files.
12. Mark job succeeded or failed.
13. Archive the job bundle when possible.

Concurrency:

- `TEMPLATE_BUILD_CONCURRENCY` defaults to `1`.
- When greater than `1`, the command starts worker threads.
- Database row locking is used to avoid double-claiming jobs.

Heartbeat/stale recovery:

- `TEMPLATE_BUILD_HEARTBEAT_SECONDS` defaults to `15`.
- `TEMPLATE_BUILD_STALE_AFTER_SECONDS` defaults to `900`.
- Stale running jobs are marked failed with `worker_restart_or_stale_claim`.

Dev bypass:

- `TEMPLATE_BUILD_DEV_BYPASS=1` skips real Packer/tool checks and writes simulated successful result files.
- This is for local development and tests, not production.

## Worker Stages

Known stages:

- `queued`: request persisted, not claimed yet.
- `preflight`: runtime, path, NAS, and storage checks.
- `assets`: ISO staging onto the NAS path.
- `init`: `packer init`.
- `validate`: `packer validate`.
- `build`: `packer build`.
- `sealing`: guest finalization, currently emitted by Windows bootstrap.
- `postprocess`: result and archive wrap-up.
- `done`: terminal display stage.

Terminal statuses:

- `succeeded`
- `failed`
- `canceled` exists in the model, but cancel controls are not implemented yet.

## ISO Staging

ISO staging happens in `core.template_builds._stage_single_iso()` and `_stage_required_isos()`.

Behavior:

- The worker downloads installer ISOs to `PACKER_NAS_ISO_DIR`.
- It writes a JSON manifest beside each staged ISO.
- Existing staged ISOs are reused when the manifest source URL matches.
- Filename conflicts get numeric suffixes such as `ubuntu-2.iso`.
- Progress is published into `result_payload.iso_stage_progress`.
- Final staged records include Proxmox `iso_file` values.
- `PROXMOX_ISO_STORAGE_POOL` defaults to `ChirpNAS_ISO_Templates`.

Windows builds stage two ISO roles:

- boot/install ISO
- VirtIO driver ISO

Linux builds stage the boot/install ISO.

## Packer/Guest Behavior

Ubuntu:

- Uses Proxmox `boot_iso` with staged `iso_file`.
- Adds a generated NoCloud `cidata` ISO through `additional_iso_files`.
- Uses SSH communicator with fixed build user credentials generated by the worker.
- Enables cloud-init and qemu agent in the Packer source.

Debian:

- Uses Proxmox `boot_iso` with staged `iso_file`.
- Serves `preseed.cfg` through Packer `http_content`.
- Uses SSH communicator with fixed build user credentials generated by the worker.
- Enables cloud-init and qemu agent in the Packer source.

Windows BIOS:

- Uses `seabios` and `pc`.
- Uses SATA disk and SATA install ISO.
- Adds staged VirtIO ISO.
- Adds generated `AUTOUNATTEND` ISO through `additional_iso_files`.
- Uses WinRM communicator.

Windows UEFI + TPM:

- Uses `ovmf` and `q35`.
- Configures EFI storage with `efi_type = "4m"`.
- Configures TPM v2.0.
- Uses SATA disk and install ISO.
- Adds staged VirtIO ISO and generated `AUTOUNATTEND` ISO.
- Uses WinRM communicator.

## VM Provisioning Flow

1. Browser loads completed templates through `GET /api/template/list/`.
2. User selects template and VM hardware/network options.
3. Browser posts to `POST /api/vm/start/`.
4. Backend verifies that the template belongs to the user and has a succeeded last build.
5. Backend validates VM name, hardware, network bridge, optional VLAN, and static network fields.
6. Backend allocates destination VMID through Proxmox `/cluster/nextid`.
7. Backend creates a `VirtualMachine` row in status `provisioning`.
8. Proxmox clone is requested from the source template VMID.
9. If Proxmox returns a task UPID, the service waits for task completion.
10. VM hardware and network config are applied.
11. Primary disk is detected from VM config.
12. Disk is resized when requested size is larger than source size.
13. VM is started.
14. The `VirtualMachine` row is marked `running`.
15. On exception, the row is marked `failed` and `last_error` is recorded.

Clone behavior currently uses `full=0`, so it is a linked clone request unless Proxmox/storage behavior changes it.

## Proxmox Integration

`ProxmoxClient`:

- Normalizes `PROXMOX_BASE_URL`.
- Accepts values with or without `/api2/json`.
- Uses `PVEAPIToken=<id>=<secret>` authorization header.
- Honors `PROXMOX_TLS_VERIFY`.
- Disables urllib3 insecure warnings when TLS verification is disabled.
- Exposes helpers for:
  - allocate next VMID
  - clone from template
  - get VM config
  - update VM config
  - resize disk
  - start VM
  - wait for task

Worker preflight also calls Proxmox storage metadata endpoints to confirm ISO and VM disk storage capabilities. Permission-limited storage metadata can be accepted with a warning when the API token cannot fully audit storage content.

## Current Constraints

- Template builds are DHCP-ready only. Static IP configuration is rejected during template creation.
- VM provisioning supports DHCP and static IPv4 payloads.
- Template creation needs `DirectoryProfile.ad_rid`; users missing a synced directory profile must sign out and sign back in.
- Windows builds require admin credentials, image selector, VirtIO ISO URL, firmware profile, and WinRM settings.
- Ansible options are persisted but not executed.
- Template/job history UI is not implemented beyond the live create flow.
- Retry/cancel controls are not implemented.
- Real acceptance builds for Ubuntu, Debian, Windows BIOS, and Windows UEFI + TPM are still required.
