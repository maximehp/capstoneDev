# Capstone Dev

Capstone is a Django app for lab VM lifecycle management with AD-backed login and Proxmox automation. The UI is server-rendered with partial navigation powered by fetch requests.

## Stack
- Django 6
- SQLite for local dev
- PostgreSQL planned for staging/production (TrueNAS)
- Proxmox REST API
- AD auth via ldap3
- Vanilla JS/CSS

## Docker Compose

The repository now includes a Compose-based development runtime that matches the documented app shape:
- `db`: PostgreSQL
- `migrate`: one-shot schema/bootstrap step
- `web`: Django development server
- `worker`: `manage.py run_template_build_worker`

Start it from the repo root:
```bash
docker compose up --build
```

The app will be available at:
```text
http://127.0.0.1:8000
```

Compose expects a local `.env` file. At minimum, set:
- `SECRET_KEY`
- `DEBUG=1`
- `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost`
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

Compose pins `DATABASE_URL` to the bundled PostgreSQL service (`db`) and uses the default development credentials `capstone/capstone/capstone`.
The container image includes `packer` and `xorriso` so the worker can execute template jobs inside Compose without depending on host-installed binaries.

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
- `DATABASE_URL` (optional; defaults to SQLite locally, PostgreSQL in Compose)
- `PROXMOX_BASE_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `PROXMOX_TLS_VERIFY`
- `AD_LDAP_HOST`
- `AD_UPN_SUFFIX`
- `AD_BASE_DN`
- `TEMPLATE_CREATION_POLICY` (`allow_all` default, `faculty_only` optional)
- `TEMPLATE_BUILD_WORKDIR`
- `TEMPLATE_BUILD_POLL_SECONDS`
- `TEMPLATE_BUILD_MAX_TIMEOUT_SEC`
- `PACKER_BIN`
- `PACKER_ISO_TOOL` (optional override for ISO authoring tool)
- `PACKER_PROXMOX_PLUGIN_SOURCE`
- `PACKER_PROXMOX_PLUGIN_VERSION`
- `ALLOW_PRIVATE_TEMPLATE_ASSET_URLS` (`1` by default)

## Notes
- AD auth is mandatory.
- ISO source URLs are unrestricted.
- `DATABASE_URL` supports `sqlite:///...` and `postgresql://...`.
- Template VMID policy: `"100" + user.id` as a string.
- Template creation policy is configurable with `TEMPLATE_CREATION_POLICY` (`allow_all` default, `faculty_only` optional).
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
- The worker process is what creates the per-job workspace and generated files:
  - copied `.pkr.hcl`
  - `user-data` / `meta-data`
  - `preseed.cfg`
  - `Autounattend.xml`
  - bootstrap script
  - `template.auto.pkrvars.json`
  - `packer.log`
- Job workspaces are created under `TEMPLATE_BUILD_WORKDIR/job-<uuid>/`.
- Packer builds are executed by the background worker:
  - `.\.venv\Scripts\python.exe manage.py run_template_build_worker`
- For local development, run both processes:
  - `.\.venv\Scripts\python.exe manage.py runserver`
  - `.\.venv\Scripts\python.exe manage.py run_template_build_worker`
- For Compose development, the one-shot `migrate` service applies migrations before `web` and `worker` start.

## Docs
See `wiki/README.md` for architecture, API notes, and the roadmap.
