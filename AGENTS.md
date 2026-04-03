# AGENTS.md

## Mission
Build and harden the Capstone Django app for lab VM lifecycle management with AD-backed login and Proxmox automation.

## Project Snapshot
- Stack: Django 6, SQLite (dev), PostgreSQL target, vanilla JS/CSS frontend, Proxmox REST API integration, ldap3 for AD auth.
- Current state: template creation/build workflow is implemented with a separate `packer-worker`, NAS-staged ISO handling, live build progress UI, and backend test coverage.
- Auth policy: AD auth is mandatory. Any authenticated user can create/configure VMs. Only faculty can create templates.
- Template VMID policy: `"100" + faculty user id` as a string.
- ISO source URLs are unrestricted.

## Agent Priorities
1. Keep app behavior correct and secure over adding new UI polish.
2. Fix configuration and integration mismatches first (env names, auth flow, API contracts).
3. Add regression tests for backend endpoints before major refactors.
4. Preserve existing visual language unless explicitly asked to redesign.

## Ground Rules
- Never commit secrets or real credentials. Use `.env` locally only.
- Treat Proxmox/AD calls as external dependencies: isolate logic, handle errors explicitly, and mock in tests.
- Keep JS framework-free unless the user asks to adopt a framework.
- Avoid breaking partial-navigation behavior (`X-Requested-With: fetch|prefetch`).
- Prefer small, reviewable PR-sized changes.
- After each major feature is completed, commit the new work before moving on.
- The user wants every source change set committed and pushed after it is validated.
- Repository remote is `origin https://github.com/maximehp/capstoneDev.git`; default branch in active use is `main`.

## Environment Contract
Ensure code and `.env` agree on naming. Current expected keys in code:
- Django: `SECRET_KEY`, `DEBUG`, `DJANGO_ALLOWED_HOSTS`
- Proxmox: `PROXMOX_BASE_URL`, `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET`, `PROXMOX_TLS_VERIFY`, `PROXMOX_NODE`, `PROXMOX_STORAGE_POOL`, `PROXMOX_ISO_STORAGE_POOL`
- AD: `AD_LDAP_HOST`, `AD_UPN_SUFFIX`, `AD_BASE_DN`
- Template/NAS runtime: `TEMPLATE_BUILD_WORKDIR`, `PACKER_JOBS_HOST_PATH`, `PACKER_NAS_HOST_PATH`, `PACKER_NAS_ROOT`, `PACKER_NAS_ISO_DIR`, `PACKER_NAS_ARCHIVE_DIR`, `PACKER_CACHE_DIR`

Current deployment facts established in this thread:
- Template ISOs are staged into `PACKER_NAS_ISO_DIR` and then referenced via Proxmox `iso_file`.
- `ChirpNAS_ISO_Templates` is a valid Proxmox storage for both `Disk image` and `ISO image`; do not assume ISO and VM disk pools must differ.
- In Compose deploys, `packer-worker` runs as UID/GID `1000:1000` to match the writable NFS export.
- Job manifests under `TEMPLATE_BUILD_WORKDIR/job-<uuid>/` must remain shared-writable because `web` creates the initial queued files and `packer-worker` rewrites them later.

## Minimum Validation Before Merge
Run from repo root:
```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

When touching API/auth code, also manually verify:
1. Login success/failure flow.
2. ISO inspect success/failure cases.
3. VM start endpoint error handling for external API failures.
4. Template build queue claim and live progress behavior when the worker is running.

## Suggested Work Sequence
1. Stabilize config and integration contracts.
2. Add backend tests (views + Proxmox/AD adapters).
3. Complete template-creation workflow backend endpoints.
4. Add persistence models/migrations for templates, classes, and VM records.
5. Improve ops readiness (logging, deployment profile, non-SQLite production DB).
