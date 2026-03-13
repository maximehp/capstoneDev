# AGENTS.md

## Mission
Build and harden the Capstone Django app for lab VM lifecycle management with AD-backed login and Proxmox automation.

## Project Snapshot
- Stack: Django 6, SQLite (dev), PostgreSQL target, vanilla JS/CSS frontend, Proxmox REST API integration, ldap3 for AD auth.
- Current state: UI foundations exist (home/settings/login + modal wizard), backend has partial APIs (`/api/vm/start/`, `/api/iso/inspect`), tests are missing.
- Auth policy: AD auth is mandatory. Any authenticated user can create/configure VMs. Only faculty can create templates.
- Template VMID policy: `"100" + faculty user id` as a string.
- ISO source URLs are unrestricted.

## Agent Priorities
1. Keep app behavior correct and secure over adding new UI polish.
2. Fix configuration and integration mismatches first (env names, auth flow, API contracts).
3. Add regression tests for backend endpoints before major refactors.
4. Preserve existing visual language unless explicitly asked to redesign.

## Ground Rules
- Never commit secrets or real credentials. Use `.env` locally only.
- Treat Proxmox/AD calls as external dependencies: isolate logic, handle errors explicitly, and mock in tests.
- Keep JS framework-free unless the user asks to adopt a framework.
- Avoid breaking partial-navigation behavior (`X-Requested-With: fetch|prefetch`).
- Prefer small, reviewable PR-sized changes.
- After each major feature is completed, commit the new work before moving on.

## Environment Contract
Ensure code and `.env` agree on naming. Current expected keys in code:
- Django: `SECRET_KEY`, `DEBUG`, `DJANGO_ALLOWED_HOSTS`
- Proxmox: `PROXMOX_BASE_URL`, `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET`, `PROXMOX_TLS_VERIFY`
- AD: `AD_LDAP_HOST`, `AD_UPN_SUFFIX`, `AD_BASE_DN`

Note: repository currently shows mixed key names; align these before feature work.

## Minimum Validation Before Merge
Run from repo root:
```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

When touching API/auth code, also manually verify:
1. Login success/failure flow.
2. ISO inspect success/failure cases.
3. VM start endpoint error handling for external API failures.

## Suggested Work Sequence
1. Stabilize config and integration contracts.
2. Add backend tests (views + Proxmox/AD adapters).
3. Complete template-creation workflow backend endpoints.
4. Add persistence models/migrations for templates, classes, and VM records.
5. Improve ops readiness (logging, deployment profile, non-SQLite production DB).
