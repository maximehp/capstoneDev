# Roadmap

This roadmap reflects the current code scan, tests, and deployment facts.

## Current State

Implemented:

- AD-backed login path with endpoint fallback and directory attribute sync.
- Settings page showing AD-derived identity/access details.
- Async template creation API.
- Template build job persistence.
- Dedicated worker command/container.
- Packer profile generation for Ubuntu autoinstall, Debian preseed, Windows BIOS, and Windows UEFI + TPM.
- NAS ISO staging before Packer build.
- Live build status API and modal progress UI.
- Saved ISO and software source history.
- Completed-template listing.
- VM provisioning from completed templates.
- Proxmox clone/config/resize/start service.
- Backend regression test coverage for many API and worker paths.
- Compose deployment shape with separate `web` and `packer-worker`.
- WhiteNoise static serving in production mode.

## High Priority

1. Reconcile template VMID policy.
   - Written policy says `"100" + faculty user id`.
   - Current code uses AD RID plus three-digit sequence.
   - Decide which is correct, then update code and docs together.

2. Run live acceptance builds.
   - Ubuntu autoinstall.
   - Debian preseed.
   - Windows BIOS.
   - Windows UEFI + TPM.

3. Harden worker operations.
   - Finish retention/cleanup policy.
   - Add documented stale queued job cleanup steps.
   - Decide whether `web` should also run as UID/GID `1000:1000`.
   - Add admin-facing storage/export validation.

4. Tighten auth policy.
   - Confirm AD group/OU/attribute that defines faculty.
   - Review whether Django `ModelBackend` should remain enabled in production.
   - Register/audit `DirectoryProfile` in admin if useful.

5. Improve template job controls.
   - Cancel queued/running jobs.
   - Retry failed jobs.
   - Template/job history UI.

## Near Term

- Add Ansible execution on top of stored metadata.
- Add structured logging for:
  - login attempts
  - template create attempts
  - job claims
  - Packer command failures
  - Proxmox provisioning actions
- Add audit events for sensitive operations.
- Add an operations page or management command that validates:
  - Proxmox API reachability
  - token permissions
  - node availability
  - ISO storage content types
  - disk storage content types
  - NAS write permissions
  - Packer/plugin readiness
- Add automated tests around any new auth/role policy.
- Add frontend or browser tests for modal flows.

## Later

- Broader role model if needed:
  - student
  - faculty/instructor
  - admin
- Production database hardening.
- Better retention and archival controls for job bundles.
- More user-facing VM inventory/history.
- Optional separation of build runner from web host if template builds become resource-heavy.
- More robust Windows build matrix once target ISOs are fixed.

## Known Gaps

- Real Proxmox/Packer acceptance has not been proven by automated tests.
- Real AD role source still needs a final policy decision.
- `canceled` job state exists, but no cancel flow exists.
- Ansible metadata is stored but not executed.
- Static IP template builds are intentionally unsupported.
- The home page does not yet show a real VM inventory.
- The legacy `database/Capstone2026USERS.db` content does not represent the current Django model.
- No automated test confirms host `/etc/fstab` remount behavior.

## Minimum Validation

Before merging code changes:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

Before considering deployment-ready changes, manually verify:

- AD login success/failure.
- ISO inspect success/failure.
- Worker claim and live progress.
- Proxmox API failure handling.
- At least one real Linux template build.
- At least one real Windows template build.
- VM provisioning from a completed template.
