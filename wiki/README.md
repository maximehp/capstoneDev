# Capstone Wiki

This folder is the living project wiki for the Capstone Django app. It documents the current codebase, runtime shape, deployment assumptions, API contracts, and remaining work.

## Project Snapshot

- Purpose: lab VM lifecycle management for authenticated users.
- Backend: Django 6 monolith with one local app, `core`.
- Database: SQLite for local development when `DATABASE_URL` is unset, PostgreSQL for Compose/deployment through `DATABASE_URL`.
- Auth: Active Directory-backed login through `ldap3`, with Django sessions.
- VM automation: Proxmox REST API integration using API tokens.
- Template automation: async Django job records plus a dedicated `packer-worker` process/container.
- Frontend: server-rendered Django templates enhanced by vanilla JavaScript, fetch-based partial navigation, and custom modal workflows.
- Static serving: Django static files locally, WhiteNoise compressed manifest storage when `DEBUG=0`.

## Pages

- [Architecture](Architecture.md): major components, request flows, worker lifecycle, auth flow, and current implementation constraints.
- [API](API.md): endpoint inventory, request/response contracts, validation rules, and error behavior.
- [Environment](Environment.md): configuration variables, defaults, deployment paths, and infrastructure assumptions.
- [Data Model](Data-Model.md): Django models, relationships, fields, migrations, and persistence notes.
- [Frontend](Frontend.md): templates, JavaScript modules, partial navigation, modals, theme behavior, and assets.
- [Operations](Operations.md): Compose deployment, NAS/fstab facts, permissions, runbook checks, troubleshooting, and cleanup guidance.
- [Testing](Testing.md): validation commands, current test coverage map, and manual verification scope.
- [Project Status](Project-Status.md): user-stated done/planned status and future feature list.
- [Implementation Inventory](Implementation-Inventory.md): file-by-file repository map from the current scan.
- [Roadmap](Roadmap.md): current gaps, next work, and stale/mismatch notes.

## Current User Flows

1. User logs in at `/login/` with Active Directory credentials.
2. Django syncs selected AD attributes into the local `User` and `DirectoryProfile`.
3. Authenticated users can open the home page and Create VM modal.
4. Users can list completed templates owned by their account.
5. Users can provision VMs from completed templates through `POST /api/vm/start/`.
6. Faculty, or any user when policy is relaxed, can create template build jobs.
7. Template creation validates the ISO, selected software, hardware, network, and profile-specific fields.
8. `POST /api/template/create/` persists `TemplateDefinition` and `TemplateBuildJob`, writes initial queue manifests, and returns HTTP `202`.
9. `packer-worker` claims queued jobs, stages ISO files onto the mounted NAS path, generates Packer inputs, and runs Packer.
10. The UI polls the build status endpoint and displays preflight checks, staged ISO progress, worker events, and errors.

## Current Build Flow

- The template modal submits to `POST /api/template/create/`.
- That request creates a `TemplateDefinition`, enqueues a `TemplateBuildJob`, and returns `202`.
- The request writes initial `request.json` and `status.json` files under `TEMPLATE_BUILD_WORKDIR/job-<uuid>/`.
- Packer is not run in the web request.
- The dedicated worker command, `manage.py run_template_build_worker`, claims queued jobs from the database.
- The worker performs runtime and Proxmox storage preflight checks.
- Installer ISOs are staged into `PACKER_NAS_ISO_DIR` before Packer starts.
- Staged ISO files are referenced through Proxmox `iso_file` values such as `ChirpNAS_ISO_Templates:iso/<filename>.iso`.
- The worker generates the remaining per-job files:
  - `generated/template.pkr.hcl`
  - `generated/user-data`
  - `generated/meta-data`
  - `generated/preseed.cfg`
  - `generated/Autounattend.xml`
  - `generated/bootstrap.sh`
  - `generated/bootstrap.ps1`
  - `generated/template.auto.pkrvars.json`
  - `logs/packer.log`
  - `results/preflight.json`
  - `results/iso-stage.json`
  - `results/software-results.json`
  - `results/result.json`
  - `results/error-summary.txt`
- The worker then runs `packer init`, `packer validate`, and `packer build -machine-readable`.

## Current Deployment Lessons

- The NAS is mounted on the Ubuntu VM that runs Docker.
- The NAS mount is configured in `/etc/fstab`, so it should automatically remount after reboot.
- Compose bind-mounts the host NAS path into both `web` and `packer-worker`.
- `packer-worker` currently runs as UID/GID `1000:1000` to match the writable NAS export.
- `web` creates queued job manifests and `packer-worker` rewrites them, so job workspace permissions must allow both services to write.
- `ChirpNAS_ISO_Templates` can be used for both VM disk images and ISO media when Proxmox reports both content types for that storage.
- Existing jobs created before permission fixes may require manual host-side cleanup or permissions repair.

## Important Current Mismatch

The original project policy said template VMIDs should be `"100" + faculty user id`. Current code no longer implements that exact rule. `core.views._template_vmid_for_user()` requires a `DirectoryProfile`, uses `DirectoryProfile.ad_rid` as the prefix, and appends a three-digit sequence for each template owned by the same user. Example: AD RID `1536` creates `1536001`, then `1536002`.

Treat the code behavior as the current truth until the policy is intentionally reconciled.

## Conventions

- Keep docs focused on committed behavior, deployed facts, and known gaps.
- Do not commit real secrets or credentials.
- Treat Proxmox, Active Directory, NAS, Packer, and package repositories as external dependencies.
- Mock external dependencies in tests.
- Preserve partial-navigation behavior that relies on `X-Requested-With: fetch` and `X-Requested-With: prefetch`.
