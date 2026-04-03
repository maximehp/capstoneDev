# TODO

## Now
- Rotate local Proxmox/AD credentials that were previously stored in `.env` and keep secrets out tracked history.
- Run real end-to-end Packer acceptance builds for:
  - Ubuntu autoinstall
  - Debian preseed
  - Windows BIOS
  - Windows UEFI + TPM
- Add an ops runbook for the Compose deployment covering:
  - `web` + `packer-worker` rebuild/restart flow
  - required host path permissions for `${PACKER_JOBS_HOST_PATH}` and `${PACKER_NAS_HOST_PATH}`
  - how to clean up stale queued job directories
  - how to inspect `logs/packer.log` and `results/iso-stage.json`
- Verify the real build host/export assumptions end to end:
  - `${PACKER_NAS_HOST_PATH}/isos` writable by container UID/GID `1000:1000`
  - `${PACKER_NAS_HOST_PATH}/Templates/packer-cache` writable by worker
  - `${PACKER_NAS_HOST_PATH}/Templates/archives` writable by worker
  - `${PACKER_JOBS_HOST_PATH}` shared-writable between `web` and `packer-worker`
- Decide whether `web` should also run as UID/GID `1000:1000` in Compose to remove cross-user job-manifest edge cases entirely.
- Keep Ansible metadata wiring in payload/model now; defer execution until post-v1.
- Add cancellation/retry controls for queued and failed template build jobs.
- Add template list/history UI for previously created definitions and jobs.

## Next
- Add Ansible configuration application for VM provisioning.
- Add real faculty-role enforcement from AD group/attribute data instead of relying on local staff/default policy configuration.
- Replace fixed Linux build credentials with generated per-job credentials if the builder flow remains stable.
- Add artifact retention/cleanup policy for old job workspaces and logs.
- Add a reusable Proxmox storage/export validation page or command for admins before first template build.
- Add structured logging and audit events.

## Later
- Role model expansion if needed beyond faculty and students.
- Operational hardening and deployment docs.
