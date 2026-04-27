# Environment

Configuration is loaded from process environment and `.env` through `python-dotenv`. Do not commit real `.env` secrets.

## Settings Loader

`capstoneDev/settings.py` provides helpers:

- `_env_str(name, default="", aliases=())`
- `_env_bool(name, default=False, aliases=())`
- `_database_settings(BASE_DIR)`

Aliases currently supported:

- `SECRET_KEY` falls back to `DJANGO_SECRET_KEY`.
- `DEBUG` falls back to `DJANGO_DEBUG`.
- `AD_LDAP_HOST` can fall back to legacy `AD_HOST` inside the auth backend.

## Django Variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `SECRET_KEY` | Required when `DEBUG=0` | `secret` | Production rejects the default secret. |
| `DEBUG` | No | `true` | Parsed from `1`, `true`, `yes`, `on`. |
| `DJANGO_ALLOWED_HOSTS` | No | `127.0.0.1,localhost` | Comma-separated. |
| `DATABASE_URL` | Required for Compose/deploy | unset | SQLite fallback when unset. |

When `DEBUG=0`, settings require:

- `SECRET_KEY`
- `PROXMOX_BASE_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `AD_LDAP_HOST`
- `AD_UPN_SUFFIX`
- `AD_BASE_DN`

## Database URL

Supported schemes:

- `sqlite:///path/to/db.sqlite3`
- `postgres://user:pass@host:5432/db`
- `postgresql://user:pass@host:5432/db`

Local fallback:

- If `DATABASE_URL` is unset, Django uses `db.sqlite3` at repo root.

Test fallback:

- When running tests outside Docker and `DATABASE_URL` points to host `db`, settings fall back to SQLite so local tests do not require the Compose network.

Deployment target:

- PostgreSQL is the intended deployment database.
- Compose requires `DATABASE_URL`.
- The deploy helper rejects `DATABASE_URL` values that still point at Docker host `db` for server deployment.

## Proxmox Variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `PROXMOX_BASE_URL` | Required in production | none | Can be host root, `/api2`, or `/api2/json`; normalized internally. |
| `PROXMOX_TOKEN_ID` | Required in production | none | Used in `PVEAPIToken` header. |
| `PROXMOX_TOKEN_SECRET` | Required in production | none | Secret, never commit. |
| `PROXMOX_TLS_VERIFY` | No | `1` | Set `0` to disable TLS verification. |
| `PROXMOX_NODE` | Required for provisioning/builds | `""` | Node used by VM provisioning and Packer variables. |
| `PROXMOX_STORAGE_POOL` | No | `local-lvm` | VM disk storage pool. |
| `PROXMOX_ISO_STORAGE_POOL` | No | `ChirpNAS_ISO_Templates` | ISO media storage pool. |

Notes:

- `PROXMOX_BASE_URL=https://host:8006` becomes `https://host:8006/api2/json`.
- `PROXMOX_BASE_URL=https://host:8006/api2` becomes `https://host:8006/api2/json`.
- `PROXMOX_BASE_URL=https://host:8006/api2/json` is used as-is.
- `PROXMOX_STORAGE_POOL` and `PROXMOX_ISO_STORAGE_POOL` may be the same storage when Proxmox reports both disk-image and ISO content.
- `ChirpNAS_ISO_Templates` is known to be valid for both VM disk image and ISO image content in the current environment.

## Active Directory Variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `AD_LDAP_HOST` | Required in production | none | Can be one host, IP, comma list, semicolon list, with optional port. |
| `AD_LDAP_PORT` | No | inferred | Defaults to 389 unless SSL/port force another value. |
| `AD_LDAP_USE_SSL` | No | inferred | Set `1` for LDAPS. |
| `AD_LDAP_CONNECT_TIMEOUT` | No | `1` | Seconds, float accepted. |
| `AD_UPN_SUFFIX` | Required in production | none | Used to bind as `username@suffix`. |
| `AD_BASE_DN` | Required in production | none | Used to query attributes after bind. |

Endpoint behavior:

- Host values can include `ldap://`, `ldaps://`, raw hostnames, IPs, or `host:port`.
- A single IP host can add the AD domain suffix as a fallback endpoint.
- LDAP bind stops retrying after an invalid credentials response from a reachable controller.
- Connectivity failures can retry other candidate endpoints.

AD attributes synced:

- `objectSid`
- `displayName`
- `givenName`
- `sn`
- `distinguishedName`
- `memberOf`
- `userPrincipalName`
- `department`
- `company`

## Template and Worker Variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `TEMPLATE_CREATION_POLICY` | No | `faculty_only` | Supported: `faculty_only`, `allow_all`. Invalid values fall back to `faculty_only`. |
| `TEMPLATE_BUILD_WORKDIR` | No | `database/packer_templates/jobs` locally | Compose default: `/var/lib/capstone/jobs`. |
| `TEMPLATE_BUILD_POLL_SECONDS` | No | `5` | Worker sleep interval when queue is empty. |
| `TEMPLATE_BUILD_MAX_TIMEOUT_SEC` | No | `10800` | Command timeout for Packer steps. |
| `TEMPLATE_BUILD_HEARTBEAT_SECONDS` | No | `15` | Intended heartbeat interval. |
| `TEMPLATE_BUILD_STALE_AFTER_SECONDS` | No | `900` | Running jobs older than this without heartbeat are recovered as failed. |
| `TEMPLATE_BUILD_CONCURRENCY` | No | `1` | Worker thread count. |
| `TEMPLATE_BUILD_DEV_BYPASS` | No | `0` | Simulates successful builds without Packer. |
| `PACKER_BIN` | No | `packer` | Compose worker sets `/usr/bin/packer`. |
| `PACKER_ISO_TOOL` | No | auto-detect | Can force `xorriso`, `mkisofs`, `genisoimage`, or `oscdimg` path/name. |
| `PACKER_PROXMOX_PLUGIN_SOURCE` | No | `github.com/hashicorp/proxmox` | Used when writing required plugin block. |
| `PACKER_PROXMOX_PLUGIN_VERSION` | No | `>= 1.1.0` | Used when writing required plugin block. |
| `PACKER_CACHE_DIR` | No | `database/packer_templates/cache` locally | Compose deploy default: `/mnt/capstone-nas/Templates/packer-cache`. |
| `PACKER_NAS_ROOT` | No | `/mnt/capstone-nas` | Root NAS mount inside containers. |
| `PACKER_NAS_ISO_DIR` | No | `/mnt/capstone-nas/isos` | Staged installer ISO destination. |
| `PACKER_NAS_ARCHIVE_DIR` | No | `/mnt/capstone-nas/archive` in settings | Compose deploy default: `/mnt/capstone-nas/Templates/archives`. |
| `APP_USERDATA_DIR` | No | `/mnt/capstone-nas/UserData` | User data root. |
| `PACKER_JOBS_HOST_PATH` | No | `/srv/capstone/packer-jobs` in Compose | Host path bound to worker/web job workdir. |
| `PACKER_NAS_HOST_PATH` | No | `/mnt/capstone-nas` in Compose | Host NAS mount path bound into containers. |
| `ALLOW_PRIVATE_TEMPLATE_ASSET_URLS` | No | `1` | Allows private/internal ISO and software URLs by default. |

## Docker Compose Defaults

`compose.yaml` services:

- `migrate`
  - image target: `web-runtime`
  - env file: `.env`
  - `RUN_MIGRATIONS=1`
  - `RUN_COLLECTSTATIC=0`
  - command: `python manage.py check`
- `web`
  - image target: `web-runtime`
  - waits for `migrate`
  - publishes `8000:8000`
  - `RUN_COLLECTSTATIC=1`
  - `RUN_MIGRATIONS=0`
  - bind mounts jobs and NAS paths
- `packer-worker`
  - image target: `packer-runtime`
  - runs as `1000:1000`
  - waits for `migrate`
  - sets worker HOME/XDG/Packer plugin temp paths under `/tmp/capstone-worker`
  - bind mounts jobs and NAS paths

`compose.dev.yaml`:

- bind mounts the repo to `/app`
- runs Django dev server for `web`
- allows empty `DATABASE_URL`
- defaults local jobs path to `./database/packer_templates/jobs`
- defaults local NAS path to `./database/nas`

## Host Paths

Deploy/server expected paths:

- Jobs: `${PACKER_JOBS_HOST_PATH:-/srv/capstone/packer-jobs}`
- NAS mount: `${PACKER_NAS_HOST_PATH:-/mnt/capstone-nas}`
- Staged ISOs: `${PACKER_NAS_HOST_PATH}/isos`
- Packer cache: `${PACKER_NAS_HOST_PATH}/Templates/packer-cache`
- Job archives: `${PACKER_NAS_HOST_PATH}/Templates/archives`
- User data: `${PACKER_NAS_HOST_PATH}/UserData`

Current infrastructure fact:

- The NAS is mounted on the Ubuntu VM that runs Docker.
- The mount is recorded in `/etc/fstab`, so the host should automatically remount the NAS after reboot.

## Permissions

Important write paths:

- `TEMPLATE_BUILD_WORKDIR`
- `PACKER_NAS_ISO_DIR`
- `PACKER_CACHE_DIR`
- `PACKER_NAS_ARCHIVE_DIR`
- `APP_USERDATA_DIR`

Current Compose worker runs as UID/GID `1000:1000`.

The job directory must be shared-writable because:

- `web` creates the initial queued manifests.
- `packer-worker` claims the job and rewrites status/result files.

The worker code also attempts to set workspace directories to `0777` and files to `0666` to avoid cross-container write failures.

## Static Files

Static configuration:

- `STATIC_URL=/static/`
- `STATICFILES_DIRS=[BASE_DIR / "static"]`
- `STATIC_ROOT=BASE_DIR / "staticfiles"`
- In debug: `django.contrib.staticfiles.storage.StaticFilesStorage`
- In production: `whitenoise.storage.CompressedManifestStaticFilesStorage`

When `RUN_COLLECTSTATIC=1`, the Docker entrypoint runs:

```bash
python manage.py collectstatic --noinput
```

## Local Development Commands

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Run worker locally:

```powershell
.\.venv\Scripts\python.exe manage.py run_template_build_worker
```

Run one worker job:

```powershell
.\.venv\Scripts\python.exe manage.py run_template_build_worker --once
```

## Compose Commands

Deploy shape:

```bash
docker compose up --build
```

Development override:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

Deploy helper:

```bash
scripts/deploy.sh
```
