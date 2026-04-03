# Wiki

This folder contains the living documentation for Capstone.

## Pages
- `wiki/Environment.md`
- `wiki/Architecture.md`
- `wiki/API.md`
- `wiki/Roadmap.md`

## Current Build Flow
- The template modal submits to `POST /api/template/create/`.
- That request creates a `TemplateDefinition`, enqueues a `TemplateBuildJob`, and returns `202`.
- The request writes an initial `request.json` and `status.json` into the per-job workspace but does not run Packer inline.
- The dedicated `packer-worker` container claims queued jobs, runs preflight checks, stages required installer ISOs onto the mounted NAS, creates the remaining workspace files, then runs `packer init`, `packer validate`, and `packer build`.
- The staged-ISO flow now uses Proxmox `iso_file` references instead of having Packer fetch installer URLs live during the build.
- The build status payload and modal now expose:
  - a dedicated `ISO staging` phase
  - staged ISO metadata
  - live transfer progress for ISO downloads
  - redacted logs and error summaries

## Current Deployment Lessons
- `packer-worker` and `web` both touch per-job files under `TEMPLATE_BUILD_WORKDIR`, so the job workspace must be writable by both services.
- In the current Compose deploy shape, `packer-worker` runs as UID/GID `1000:1000` so it can write to the NFS-mounted TrueNAS export.
- Existing queued jobs created before permission fixes may still need manual cleanup or host-side `chmod -R a+rwX` on the jobs path.
- `ChirpNAS_ISO_Templates` can be used for both VM disks and ISO media if Proxmox reports both content types for that storage; the app no longer rejects that shared-storage layout.

## Conventions
- Keep docs focused on current behavior or committed decisions.
- Note assumptions when behavior is not yet implemented.
- Avoid committing secrets. Use `.env` locally only.
