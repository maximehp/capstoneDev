# TODO

## Now
- Rotate local Proxmox/AD credentials that were previously stored in `.env` and keep secrets out tracked history.
- Run real end-to-end Packer acceptance builds for:
  - Ubuntu autoinstall
  - Debian preseed
  - Windows BIOS
  - Windows UEFI + TPM
- Add an ops runbook for running `manage.py run_template_build_worker` under a service manager in dev/prod.
- Verify host prerequisites on the real build host:
  - `packer`
  - Proxmox plugin compatibility
  - `oscdimg` or another supported ISO authoring tool
- Decide whether to keep same-host worker execution or move builds to a separate runner.
- Keep `allow_all` as the current default policy but plan the switch to `faculty_only` later.
- Keep Ansible metadata wiring in payload/model now; defer execution until post-v1.
- Add cancellation/retry controls for queued and failed template build jobs.
- Add template list/history UI for previously created definitions and jobs.

## Next
- Add Ansible configuration application for VM provisioning.
- Add real faculty-role enforcement from AD group/attribute data instead of relying on local staff/default policy configuration.
- Replace fixed Linux build credentials with generated per-job credentials if the builder flow remains stable.
- Add artifact retention/cleanup policy for old job workspaces and logs.
- Migrate deployment profile to PostgreSQL on TrueNAS.
- Add structured logging and audit events.

## Later
- Role model expansion if needed beyond faculty and students.
- Operational hardening and deployment docs.
