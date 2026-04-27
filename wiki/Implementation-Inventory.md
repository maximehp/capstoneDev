# Implementation Inventory

This is a current file-by-file map from the repository scan.

## Root

- `AGENTS.md`
  - Project instructions, environment contract, validation policy, deployment facts, and workflow preferences.
- `README.md`
  - Developer quickstart, Compose overview, environment variable list, current notes, and production notes.
- `PROJECT_PLAN.md`
  - Older phase plan and risk analysis. Some items are stale relative to current code.
- `TODO.md`
  - Current task list and operational gaps.
- `manage.py`
  - Django command entrypoint.
- `requirements.txt`
  - Runtime dependencies.
- `pyproject.toml`
  - Project metadata and dependency list.
- `uv.lock`
  - Lock file from earlier tooling.
- `.env.example`
  - Example environment values with placeholders.
- `.env`
  - Local environment file. Do not commit secrets.
- `.gitignore`
  - Ignores `.env`, SQLite transient files, pyc files, and generated packer template files.
- `.dockerignore`
  - Excludes Git, IDE, virtualenv, pycache, pyc, root SQLite DB, and generated packer template files from Docker build context.
- `Dockerfile`
  - Multi-stage image for `web-runtime` and `packer-runtime`.
- `compose.yaml`
  - Production/deploy Compose shape with `migrate`, `web`, and `packer-worker`.
- `compose.dev.yaml`
  - Local Compose override with source bind mounts and dev server.
- `docker-entrypoint.sh`
  - Waits for PostgreSQL, runs optional migrations/static collection, then execs command.
- `LICENSE`
  - MIT license.

## Django Project Package

- `capstoneDev/__init__.py`
  - Empty package marker.
- `capstoneDev/settings.py`
  - Environment loading, database selection, auth backends, static files, logging, template/Packer settings, Proxmox settings.
- `capstoneDev/urls.py`
  - Routes pages and API endpoints.
- `capstoneDev/asgi.py`
  - Standard ASGI entrypoint.
- `capstoneDev/wsgi.py`
  - Standard WSGI entrypoint.

## Core App

- `core/__init__.py`
  - Empty package marker.
- `core/apps.py`
  - App config.
- `core/models.py`
  - `IsoSource`, `SoftwareSource`, `DirectoryProfile`, `TemplateDefinition`, `TemplateBuildJob`, `VirtualMachine`.
- `core/admin.py`
  - Admin registrations for source history, templates, jobs, and VMs.
- `core/auth_backends.py`
  - Active Directory authentication, endpoint fallback, attribute sync, role inference, directory profile sync.
- `core/ad_debug.py`
  - Helper for dumping AD attributes by binding as a user.
- `core/packer_profiles.py`
  - Build profile constants, Windows firmware/image selector constants, profile-to-target OS mapping.
- `core/views.py`
  - Page views, login/logout, VM provisioning API, ISO/software inspect APIs, saved source APIs, software validation, template create API, build status API.
- `core/template_builds.py`
  - Template build queueing, worker claim/recovery, status payloads, workspace/manifests, preflight, ISO staging, Packer artifact generation, command execution, log/error parsing, dev bypass.
- `core/tests.py`
  - Backend regression test suite.

## Management Commands

- `core/management/__init__.py`
  - Package marker.
- `core/management/commands/__init__.py`
  - Package marker.
- `core/management/commands/run_template_build_worker.py`
  - Polling worker command, optional `--once`, optional `--sleep`, optional concurrency via settings.

## Proxmox Integration

- `core/proxmox/__init__.py`
  - Package marker.
- `core/proxmox/client.py`
  - Proxmox REST client with token auth, TLS option, API base normalization, clone/config/resize/start/task helpers.
- `core/proxmox/services.py`
  - Higher-level VM provisioning service that allocates VMID, clones template, configures hardware/network, resizes disk, starts VM, and persists `VirtualMachine`.

## Packer Templates

- `core/packer/templates/ubuntu_autoinstall.pkr.hcl`
  - Proxmox ISO builder for Ubuntu autoinstall with generated NoCloud ISO and SSH provisioner.
- `core/packer/templates/debian_preseed.pkr.hcl`
  - Proxmox ISO builder for Debian preseed with HTTP-served preseed and SSH provisioner.
- `core/packer/templates/windows_unattend_bios.pkr.hcl`
  - Proxmox ISO builder for Windows BIOS with staged VirtIO ISO, generated `AUTOUNATTEND`, and WinRM provisioner.
- `core/packer/templates/windows_unattend_uefi.pkr.hcl`
  - Proxmox ISO builder for Windows UEFI + TPM with staged VirtIO ISO, generated `AUTOUNATTEND`, and WinRM provisioner.

## Migrations

- `core/migrations/0001_initial.py`
  - Source history models.
- `core/migrations/0002_templatebuildjob_templatedefinition_and_more.py`
  - Template/job models.
- `core/migrations/0003_templatedefinition_build_profile.py`
  - Build profile field.
- `core/migrations/0004_templatebuildjob_last_heartbeat_at.py`
  - Job heartbeat.
- `core/migrations/0005_directoryprofile.py`
  - AD directory profile.
- `core/migrations/0006_virtualmachine_and_more.py`
  - Provisioned VM records.
- `core/migrations/__init__.py`
  - Package marker.

## Templates

- `templates/base.html`
  - Shared layout, static/theme includes, header, Vanta background, partial-navigation regions.
- `templates/home.html`
  - Home grid and modal include.
- `templates/login.html`
  - Login form.
- `templates/settings.html`
  - Settings/account/theme page.
- `templates/partials/create_vm_modal.html`
  - VM provisioning scene and embedded template creation scene.
- `templates/partials/create_template_modal.html`
  - Six-step template creation wizard and build progress view.

## Static JavaScript

- `static/js/base.js`
  - Theme handling and partial navigation.
- `static/js/home.js`
  - Placeholder home interactions.
- `static/js/login.js`
  - Login form JSON handling.
- `static/js/modals.js`
  - Create VM and Create Template modal workflows.
- `static/js/settings.js`
  - Settings tabs and theme selector binding.
- `static/js/test.js`
  - Legacy/manual start VM helper.
- `static/js/helpers/vanta.js`
  - Vanta topology background lifecycle.

## Static CSS

- `static/css/base.css`
  - Global shell and header.
- `static/css/home.css`
  - Home tile grid.
- `static/css/login.css`
  - Login card.
- `static/css/modals.css`
  - Modal wizard and build progress UI.
- `static/css/settings.css`
  - Settings page.
- `static/css/themes/dark.css`
  - Dark theme variables.
- `static/css/themes/light.css`
  - Light theme variables.

## Static Assets

- `static/assets/images/bsu_logo.png`
  - Header logo.
- `static/assets/images/settings_icon.svg`
  - Settings link icon.

## Docker/Scripts

- `docker/packer-worker/start.sh`
  - Worker container startup script.
- `scripts/deploy.sh`
  - Host deployment helper.

## Database Folder

- `database/README.md`
  - Notes for a legacy/simple SQLite DB.
- `database/schemaCapstone2026.sql`
  - Legacy `users` table schema.
- `database/Capstone2026USERS.db`
  - Legacy/reference SQLite DB.
- `database/packer_templates/.gitignore`
  - Keeps generated packer template files out of Git.
- `database/packer_templates/jobs/...`
  - Generated job workspace content. Should usually be treated as runtime output.

## Wiki

- `wiki/README.md`
  - Wiki index and project snapshot.
- `wiki/Architecture.md`
  - Architecture and flow details.
- `wiki/API.md`
  - API contracts.
- `wiki/Environment.md`
  - Environment and deployment configuration.
- `wiki/Data-Model.md`
  - Django model documentation.
- `wiki/Frontend.md`
  - Frontend implementation notes.
- `wiki/Operations.md`
  - Deployment/runbook/troubleshooting.
- `wiki/Testing.md`
  - Test coverage and validation.
- `wiki/Implementation-Inventory.md`
  - This file.
- `wiki/Roadmap.md`
  - Next work and known gaps.
