# Roadmap

This roadmap reflects the current code scan, tests, and deployment facts.

See [Project Status](Project-Status.md) for the user-stated done/planned feature list as of April 27, 2026.

## Current State

Implemented:

- Django setup.
- Website UI.
- AD-backed login path with endpoint fallback and directory attribute sync.
- Authentication.
- Settings page showing AD-derived identity/access details.
- Async template creation API.
- Template build job persistence.
- Dedicated worker command/container.
- Packer input and output handling.
- Packer profile generation for Ubuntu autoinstall, Debian preseed, Windows BIOS, and Windows UEFI + TPM.
- Packer connection with Proxmox.
- NAS mounted on the Docker host VM.
- NAS remount configured through `/etc/fstab`.
- NAS ISO staging before Packer build.
- Proxmox API endpoint integration.
- Input validation, mostly complete.
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

3. Complete the full lab spin-up flow from Packer-created templates.
   - The code has provisioning plumbing, but the class/lab workflow is still planned.
   - Labs need to become available through classes, templates, Ansible configuration, timers, and access delivery.

4. Harden worker operations.
   - Finish retention/cleanup policy.
   - Add documented stale queued job cleanup steps.
   - Decide whether `web` should also run as UID/GID `1000:1000`.
   - Add admin-facing storage/export validation.

5. Tighten auth policy.
   - Confirm AD group/OU/attribute that defines faculty.
   - Review whether Django `ModelBackend` should remain enabled in production.
   - Register/audit `DirectoryProfile` in admin if useful.

6. Improve template job controls.
   - Cancel queued/running jobs.
   - Retry failed jobs.
   - Template/job history UI.

## Near Term

- Add Ansible execution on top of stored metadata.
- Add Apache reverse proxy.
- Add Apache Guacamole and `guacd`.
- Add Apache-to-Guacamole connection.
- Add classes that students can join for class-specific preconfigured labs.
- Add class join codes and possible QR codes.
- Add lab timer support with end-after-duration, inactivity timeout, and extension.
- Add structured logging for:
  - login attempts
  - template create attempts
  - job claims
  - Packer command failures
  - Proxmox provisioning actions
- Add audit events for sensitive operations.
- Add website tracking, analytics, and user metrics.
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
- Add CI/CD pipeline for code.
- Add logging and monitoring.
- Run security hardening and pen testing work.

## Later

- Broader role model if needed:
  - student
  - faculty/instructor
  - admin
- Template sharing.
- Auto grading based on lab state, maybe.
- Production database hardening.
- Better retention and archival controls for job bundles.
- More user-facing VM inventory/history.
- Optional separation of build runner from web host if template builds become resource-heavy.
- More robust Windows build matrix once target ISOs are fixed.

## Known Gaps

- Real Proxmox/Packer acceptance has not been proven by automated tests.
- Full lab spin-up from Packer-created templates is not complete as a product workflow.
- Real AD role source still needs a final policy decision.
- `canceled` job state exists, but no cancel flow exists.
- Ansible metadata is stored but not executed.
- Apache reverse proxy is not implemented.
- Guacamole/guacd access is not implemented.
- Classes, class codes, QR codes, and class-specific lab access are not implemented.
- Lab timers and inactivity shutdown are not implemented.
- Website tracking/analytics/user metrics are not implemented.
- CI/CD is not implemented.
- Template sharing is not implemented.
- Auto grading is not implemented.
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
