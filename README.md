# Capstone Dev

Capstone is a Django app for lab VM lifecycle management with AD-backed login and Proxmox automation. The UI is server-rendered with partial navigation powered by fetch requests.

## Stack
- Django 6
- SQLite for local dev
- PostgreSQL for Compose/staging/production via `DATABASE_URL`
- Proxmox REST API
- AD auth via ldap3
- Vanilla JS/CSS

## Docker Compose

The repository now includes a Compose-based runtime with a dedicated Packer worker container:
- `migrate`: one-shot schema/bootstrap step
- `web`: Django web app image
- `packer-worker`: `manage.py run_template_build_worker` in its own image with `packer` and ISO tooling

Production/deploy shape assumptions:
- PostgreSQL is external and must be reachable via `DATABASE_URL`
- active build workspaces stay local on the Ubuntu host
- persistent files live on the mounted TrueNAS path

Server/deploy shape:
```bash
docker compose up --build
```

Optional local development override with source bind mounts:
```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

The app will be available at:
```text
http://127.0.0.1:8000
```

Compose expects a local `.env` file. At minimum, set:
- `SECRET_KEY`
- `DEBUG=1`
- `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost`
- `DATABASE_URL`
- `AD_LDAP_HOST`
- `AD_UPN_SUFFIX`
- `AD_BASE_DN`
- `PROXMOX_BASE_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `PROXMOX_TLS_VERIFY`

You can start from:
```bash
cp .env.example .env
```

Compose expects these host paths in the deploy/server shape:
- `PACKER_JOBS_HOST_PATH` default `/srv/capstone/packer-jobs`
- `PACKER_NAS_HOST_PATH` default `/mnt/capstone-nas`

Recommended TrueNAS-backed runtime paths:
- `/mnt/capstone-nas/isos`
- `/mnt/capstone-nas/Templates/archives`
- `/mnt/capstone-nas/Templates/packer-cache`
- `/mnt/capstone-nas/UserData`

The `packer-worker` image includes `packer`, `xorriso`, `curl`, and `jq`. The `web` image does not include Packer.
When `DEBUG=0`, the `web` container now runs `collectstatic` on startup and serves collected assets with WhiteNoise.

## Development Quickstart

### Prerequisites
- Git
- Python 3.12

### macOS / Linux

Install Python 3.12 if needed:
```bash
python3 --version
```

macOS (Homebrew):
```bash
brew install python@3.12
```

Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

Clone the repository:
```bash
git clone https://github.com/maximehp/capstoneDev.git
cd capstoneDev
```

Create and activate a virtual environment:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
python3 -m pip install -r requirements.txt
```

Run the app:
```bash
python3 manage.py migrate
python3 manage.py runserver
```

### Windows (PowerShell)

Verify Python 3.12:
```powershell
py -3.12 --version
```

Install Python if needed:
- Download from https://www.python.org/downloads/
- Check "Add Python to PATH" during installation

Clone the repository:
```powershell
git clone https://github.com/maximehp/capstoneDev.git
cd capstoneDev
```

Create and activate a virtual environment:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:
```powershell
py -m pip install -r requirements.txt
```

Run the app:
```powershell
py manage.py migrate
py manage.py runserver
```

### Access the application
```
http://127.0.0.1:8000
```

This setup uses Django's built-in development server and is intended for local development only.

## Environment Variables
The app expects these keys to be set in `.env` or the environment.
- `SECRET_KEY`
- `DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL` (optional locally; required for Compose deployment)
- `PROXMOX_BASE_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `PROXMOX_TLS_VERIFY`
- `PROXMOX_NODE`
- `PROXMOX_STORAGE_POOL`
- `PROXMOX_ISO_STORAGE_POOL`
- `AD_LDAP_HOST`
- `AD_UPN_SUFFIX`
- `AD_BASE_DN`
- `TEMPLATE_CREATION_POLICY` (`faculty_only` default, `allow_all` optional)
- `TEMPLATE_BUILD_WORKDIR`
- `TEMPLATE_BUILD_POLL_SECONDS`
- `TEMPLATE_BUILD_MAX_TIMEOUT_SEC`
- `PACKER_BIN`
- `PACKER_ISO_TOOL` (optional override for ISO authoring tool)
- `PACKER_PROXMOX_PLUGIN_SOURCE`
- `PACKER_PROXMOX_PLUGIN_VERSION`
- `PACKER_CACHE_DIR`
- `PACKER_NAS_ROOT`
- `PACKER_NAS_ISO_DIR`
- `PACKER_NAS_ARCHIVE_DIR`
- `APP_USERDATA_DIR`
- `PACKER_JOBS_HOST_PATH`
- `PACKER_NAS_HOST_PATH`
- `TEMPLATE_BUILD_HEARTBEAT_SECONDS`
- `TEMPLATE_BUILD_STALE_AFTER_SECONDS`
- `TEMPLATE_BUILD_CONCURRENCY`
- `ALLOW_PRIVATE_TEMPLATE_ASSET_URLS` (`1` by default)

## Notes
- AD auth is mandatory.
- ISO source URLs are unrestricted.
- `DATABASE_URL` supports `sqlite:///...` and `postgresql://...`.
- `PROXMOX_BASE_URL` may be set either to the Proxmox host root (for example `https://proxmox.example:8006`) or the API root ending in `/api2/json`; the app normalizes both forms.
- Template VMID policy: `"100" + user.id` as a string.
- Template creation policy is configurable with `TEMPLATE_CREATION_POLICY` (`faculty_only` default, `allow_all` optional).
- `GET /api/template/list/` returns the authenticated user's completed templates that are ready for VM provisioning.
- `POST /api/vm/start/` now provisions a VM from a stored `TemplateDefinition`, allocates the destination VMID server-side, applies requested hardware/network config, starts the VM, and persists a `VirtualMachine` record in Django.
- Template wizard currently uses explicit build profiles:
  - `ubuntu_autoinstall`
  - `debian_preseed`
  - `windows_unattend`
- Windows template builds now require:
  - `admin_username`
  - `admin_password`
  - `image_selector_type`
  - `image_selector_value`
  - `virtio_iso_url`
  - `firmware_profile`
- Template builds are DHCP-ready only. Static IP configuration is intentionally rejected during template creation.
- `POST /api/template/create/` creates a `TemplateDefinition`, enqueues a `TemplateBuildJob`, and returns `202`.
- Hitting `Create template` does not run Packer inline in the request.
- Django writes an initial `request.json` and `status.json` into the per-job workspace when the job is queued.
- The `packer-worker` process is what creates the remaining per-job files and runs Packer:
  - `generated/template.pkr.hcl`
  - `generated/user-data` / `generated/meta-data`
  - `generated/preseed.cfg`
  - `generated/Autounattend.xml`
  - `generated/bootstrap.sh` or `generated/bootstrap.ps1`
  - `generated/template.auto.pkrvars.json`
  - `logs/packer.log`
  - `results/result.json`
  - `results/software-results.json`
  - `results/preflight.json`
  - `results/iso-stage.json`
  - `results/error-summary.txt`
- Job workspaces are created under `TEMPLATE_BUILD_WORKDIR/job-<uuid>/`.
- The worker updates job heartbeat and marks stale running jobs as failed on restart.
- The status API does not expose raw container filesystem paths.
- For Ubuntu server deployment, mount the NAS on the host and bind-mount it into `web` and `packer-worker`; the final template artifact still lives in Proxmox storage.
- Template ISOs are staged into `PACKER_NAS_ISO_DIR` first, then referenced from the Proxmox ISO storage configured by `PROXMOX_ISO_STORAGE_POOL` (default `ChirpNAS_ISO_Templates`).
- The build progress page now has a dedicated `ISO staging` step with byte/progress/speed reporting during staged ISO downloads.
- `ChirpNAS_ISO_Templates` is a valid Proxmox storage choice for both VM disks and ISOs if Proxmox reports both `Disk image` and `ISO image` content for that storage.
- `web` writes the initial queued job manifests and `packer-worker` rewrites them later, so queued job files under `TEMPLATE_BUILD_WORKDIR` must remain shared-writable between both services.
- In the Compose deploy shape, `packer-worker` runs as UID/GID `1000:1000` to match the writable NAS export on the Ubuntu host.
- The Create VM modal now loads completed templates from the app, lets the user choose hardware/network settings, and submits a real provisioning request instead of the previous placeholder clone/start path.
- For local development, run both processes:
  - `.\.venv\Scripts\python.exe manage.py runserver`
  - `.\.venv\Scripts\python.exe manage.py run_template_build_worker`
- For Compose deployment, the one-shot `migrate` service applies migrations before `web` and `packer-worker` start.
- A deploy helper is provided at `scripts/deploy.sh`.

## Current Production Notes
- If template jobs stay `Queued` forever, check `docker compose logs packer-worker` first. The most common causes seen so far were:
  - the worker could not rewrite job manifests under `/var/lib/capstone/jobs/...`
  - the NAS export allowed host UID `1000:1000` writes but squashed container root
- If template ISO staging fails immediately, verify:
  - `PACKER_NAS_ISO_DIR` exists and is writable by the `packer-worker` container user
  - `PROXMOX_STORAGE_POOL` and `PROXMOX_ISO_STORAGE_POOL` are both set correctly in `.env`
  - the configured Proxmox storage exposes the required content types (`iso` for staged installer media, `images` or equivalent disk-image content for VM disks)
- Logs for a given job live under:
  - host: `${PACKER_JOBS_HOST_PATH}/job-<uuid>/`
  - container: `${TEMPLATE_BUILD_WORKDIR}/job-<uuid>/`
  - primary files: `logs/packer.log`, `results/preflight.json`, `results/iso-stage.json`, `results/result.json`, `results/error-summary.txt`

## Docs
See `wiki/README.md` for architecture, API notes, and the roadmap.
