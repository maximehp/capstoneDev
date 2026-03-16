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
- The dedicated `packer-worker` container claims queued jobs, creates the remaining workspace files, runs `packer init`, `packer validate`, and `packer build`, and writes redacted logs/results.

## Conventions
- Keep docs focused on current behavior or committed decisions.
- Note assumptions when behavior is not yet implemented.
- Avoid committing secrets. Use `.env` locally only.
