# Architecture

## Overview
Capstone is a Django monolith with one app (`core`). Pages are server-rendered and enhanced with fetch-based partial navigation.

## Components
- Django views render full pages and optional fragments for partial navigation.
- AD authentication via `ldap3` in a custom auth backend.
- Proxmox REST API integration for VM cloning and start operations.
- Docker Compose runs separate `web` and `packer-worker` containers against the same PostgreSQL database.
- Frontend is vanilla JS/CSS and depends on consistent `X-Requested-With` headers for fragment requests.
- Template wizard is profile-driven and currently supports:
  - `ubuntu_autoinstall`
  - `debian_preseed`
  - `windows_unattend`
- Template wizard Step 2 uses a single software input (`URL` or `package`) plus a selectable list for saved/added software items.
- `POST /api/template/validate-software/` normalizes software selections before create-time validation.
- `POST /api/template/create/` persists a `TemplateDefinition`, creates a queued `TemplateBuildJob`, and returns async job metadata.
- `GET /api/template/builds/<job_uuid>/status/` exposes lifecycle state plus structured result data.
- `manage.py run_template_build_worker` claims queued jobs and runs the Packer workflow in the background.
- The worker container uses Postgres as the job queue source of truth and a shared filesystem only for workspaces, logs, and generated artifacts.
- In the current Compose deploy shape, `packer-worker` runs as UID/GID `1000:1000` to match the writable NAS export.

## External Dependencies
- Active Directory for authentication.
- Proxmox for VM lifecycle actions.
- Packer is now part of the template creation pipeline.
- Ansible metadata is stored with template requests but execution is still deferred.
- Current software validation checks URL reachability/metadata, infers artifact/strategy, applies OS compatibility rules, and feeds the generated bootstrap scripts used by the worker.

## Template Build Pipeline
1. User submits the modal with a `build_profile`.
2. Backend validates the ISO, software payload, hardware, networking, and any Windows-specific fields.
3. Backend stores:
   - `TemplateDefinition`
   - `TemplateBuildJob`
4. Worker creates a per-job workspace under `TEMPLATE_BUILD_WORKDIR/job-<uuid>/`.
5. Django writes `request.json` and initial `status.json`.
6. Worker runs preflight checks for:
   - worker runtime tools
   - writable NAS/job paths
   - Proxmox storage capabilities for ISO and disk-image content
7. Worker stages required installer ISOs into `PACKER_NAS_ISO_DIR` and records `results/iso-stage.json`.
8. Worker writes generated artifacts:
   - Ubuntu: `user-data`, `meta-data`
   - Debian: `preseed.cfg`
   - Windows: `Autounattend.xml`
   - all profiles: bootstrap script, `template.auto.pkrvars.json`, `packer.log`, and result manifests
9. Worker runs:
   - `packer init`
   - `packer validate`
   - `packer build -machine-readable`
10. Status API reports `queued`, `preflight`, `assets`, `init`, `validate`, `build`, `sealing`, `postprocess`, `done`.
11. The build page shows staged ISO metadata and live transfer progress while the worker is in `assets`.

## Data Model
- `TemplateDefinition`
  - owner, template name, VMID, build profile, target OS, ISO metadata, normalized payload snapshot, hardware/network/windows/ansible options
- `TemplateBuildJob`
  - async status/stage, timestamps, workspace/log/template paths, payload snapshot, result payload, exit code, error summary

## Current Constraints
- Template networking is DHCP-only.
- VMID policy remains `"100" + user.id`.
- Template creation policy defaults to `allow_all` and can be switched to `faculty_only`.
- The `web` container does not include `packer`; only the `packer-worker` image does.
- `web` creates the queued job manifests and `packer-worker` rewrites them later, so job workspaces under `TEMPLATE_BUILD_WORKDIR` must remain shared-writable.
- `ChirpNAS_ISO_Templates` may be used for both VM disks and staged ISO media if Proxmox reports both content types for that storage.
- Unsupported OSes are not part of the automated Packer path in the current implementation.
