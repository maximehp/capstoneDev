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
- `TEMPLATE_BUILD_POLL_SECONDS`
- `TEMPLATE_BUILD_MAX_TIMEOUT_SEC`
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
- Compose uses PostgreSQL with `db` as the hostname and runs the app in separate `migrate`, `web`, and `worker` containers.
- If `DATABASE_URL` is unset outside Compose, Django falls back to `db.sqlite3`.
- Template software validation is backend-driven (`POST /api/template/validate-software/`).
- Template creation is asynchronous. The worker command must be running to consume queued jobs:
  - `.\.venv\Scripts\python.exe manage.py run_template_build_worker`
- Packer workspace files are created only when the worker claims and executes a queued job.
