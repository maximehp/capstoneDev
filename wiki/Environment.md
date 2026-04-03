# Environment

## Required Variables
- `SECRET_KEY`
- `DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL` (required for PostgreSQL deployments, optional for SQLite local dev)
- `PROXMOX_BASE_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `PROXMOX_TLS_VERIFY`
- `PROXMOX_NODE`
- `PROXMOX_STORAGE_POOL`
- `PROXMOX_ISO_STORAGE_POOL`
- `TEMPLATE_CREATION_POLICY` (`allow_all` or `faculty_only`)
- `TEMPLATE_BUILD_WORKDIR`
- `PACKER_BIN`
- `PACKER_PROXMOX_PLUGIN_SOURCE`
- `PACKER_PROXMOX_PLUGIN_VERSION`
- `AD_LDAP_HOST`
- `AD_UPN_SUFFIX`
- `AD_BASE_DN`

## Optional / Operational Variables
- `PACKER_ISO_TOOL`
- `PACKER_CACHE_DIR`
- `PACKER_NAS_ROOT`
- `PACKER_NAS_ISO_DIR`
- `PACKER_NAS_ARCHIVE_DIR`
- `PACKER_JOBS_HOST_PATH`
- `PACKER_NAS_HOST_PATH`
- `TEMPLATE_BUILD_POLL_SECONDS`
- `TEMPLATE_BUILD_MAX_TIMEOUT_SEC`
- `TEMPLATE_BUILD_HEARTBEAT_SECONDS`
- `TEMPLATE_BUILD_STALE_AFTER_SECONDS`
- `TEMPLATE_BUILD_CONCURRENCY`
- `ALLOW_PRIVATE_TEMPLATE_ASSET_URLS`
- `AD_LDAP_PORT`
- `AD_LDAP_USE_SSL`
- `AD_LDAP_CONNECT_TIMEOUT`

## Notes
- AD auth is mandatory.
- ISO source URLs are unrestricted.
- Template VMID policy is `"100" + user.id` as a string.
- Faculty detection criteria must be defined in AD (group, OU, or attribute).
- Production target is PostgreSQL hosted on TrueNAS.
- Compose uses PostgreSQL with `db` as the hostname and runs the app in separate `migrate`, `web`, and `packer-worker` containers.
- The server/deploy Compose shape expects host bind mounts for jobs, cache, and the NAS mount.
- `PACKER_NAS_ISO_DIR` is where the worker stages installer ISOs before Packer starts.
- `PROXMOX_ISO_STORAGE_POOL` defaults to `ChirpNAS_ISO_Templates`.
- `PROXMOX_STORAGE_POOL` and `PROXMOX_ISO_STORAGE_POOL` may point to the same Proxmox storage if that storage exposes both ISO and disk-image content.
- In the current Compose deploy shape, `packer-worker` runs as UID/GID `1000:1000` because the NFS export allows host UID-based writes but squashes container root.
- If `DATABASE_URL` is unset outside Compose, Django falls back to `db.sqlite3`.
- When running tests outside Docker and `DATABASE_URL` points at the Compose host `db`, Django falls back to SQLite automatically.
- Template software validation is backend-driven (`POST /api/template/validate-software/`).
- Template creation is asynchronous. The worker command must be running to consume queued jobs:
  - `.\.venv\Scripts\python.exe manage.py run_template_build_worker`
- Packer workspace files are created only when the worker claims and executes a queued job.
- The per-job workspace under `TEMPLATE_BUILD_WORKDIR/job-<uuid>/` must be writable by both `web` and `packer-worker`.
