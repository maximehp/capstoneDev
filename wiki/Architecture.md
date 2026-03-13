# Architecture

## Overview
Capstone is a Django monolith with one app (`core`). Pages are server-rendered and enhanced with fetch-based partial navigation.

## Components
- Django views render full pages and optional fragments for partial navigation.
- AD authentication via `ldap3` in a custom auth backend.
- Proxmox REST API integration for VM cloning and start operations.
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
5. Worker writes generated artifacts:
   - Ubuntu: `user-data`, `meta-data`
   - Debian: `preseed.cfg`
   - Windows: `Autounattend.xml`
   - all profiles: bootstrap script, `template.auto.pkrvars.json`, `packer.log`
6. Worker runs:
   - `packer init`
   - `packer validate`
   - `packer build -machine-readable`
7. Status API reports `queued`, `preflight`, `init`, `validate`, `build`, `sealing`, `postprocess`, `done`.

## Data Model
- `TemplateDefinition`
  - owner, template name, VMID, build profile, target OS, ISO metadata, normalized payload snapshot, hardware/network/windows/ansible options
- `TemplateBuildJob`
  - async status/stage, timestamps, workspace/log/template paths, payload snapshot, result payload, exit code, error summary

## Current Constraints
- Template networking is DHCP-only.
- VMID policy remains `"100" + user.id`.
- Template creation policy defaults to `allow_all` and can be switched to `faculty_only`.
- Unsupported OSes are not part of the automated Packer path in the current implementation.
