# Project Plan

## Current Analysis (March 13, 2026)
- Core app is a Django monolith with one app (`core`) and server-rendered pages enhanced by fetch-based partial navigation.
- Authentication path exists for AD and Django sessions and now includes endpoint fallback handling for multi-controller LDAP targets.
- Proxmox integration can clone and start VMs, and the template build path is now modeled and persisted in Django.
- The template wizard is profile-driven and backed by async job creation plus a worker-based Packer pipeline.
- Test coverage now exists for API behavior, AD endpoint retry logic, worker execution, and generated artifact regressions (`19` tests currently).

## Current High-Risk Gaps
1. Real build-host acceptance:
   - The app-side worker and file generation are implemented, but the real environment still needs live validation against Proxmox, `packer`, plugin resolution, and ISO tooling.
2. Worker operations:
   - The queue is consumed by a management command worker and still needs deployment/runbook hardening.
3. Template authorization policy:
   - Runtime policy is configurable and defaults to `allow_all`; the intended long-term policy is tighter.
4. Windows sealing and guest tooling:
   - The generated Windows path now performs WinRM bootstrap, guest-agent install, and Sysprep, but should be validated against the exact Windows ISOs you will use.

## Execution Plan

### Phase 1: Validate the Real Template Build Loop
1. Run one real Ubuntu build, one Debian build, and one Windows build on the target app host.
2. Confirm worker preflight succeeds with the host's `packer`, plugin, and ISO authoring tool.
3. Capture and fix any builder-specific boot command, communicator, or Proxmox storage issues.

Acceptance criteria:
- At least one Linux and one Windows template build complete successfully against the real Proxmox target.
- Generated status payloads and logs are sufficient to diagnose failures without shelling into the worker manually.

### Phase 2: Harden Operations
1. Add a proper service/runbook for `run_template_build_worker`.
2. Define workspace retention and cleanup.
3. Add structured logs around queue claims, build completion, and external command failures.

Acceptance criteria:
- Worker operation is reproducible across dev and deployment environments.
- Old workspaces/logs do not accumulate indefinitely.

### Phase 3: Tighten Authorization and Provisioning
1. Switch from permissive/default template creation to the intended faculty-only policy when AD role data is ready.
2. Add Ansible execution on top of the existing stored ansible metadata.
3. Expose template/job history and retry/cancel controls in the UI.

Acceptance criteria:
- Template creation policy is enforced by actual role data rather than a temporary runtime default.
- Post-build provisioning can apply additional configuration without schema changes.

### Phase 4: Production Readiness (Week 4+)
1. Move from SQLite to PostgreSQL for deployment profile.
2. Add structured logging and audit events (login attempts, provisioning actions).
3. Improve deployment docs and container strategy.
4. Add role model (student/instructor/admin) and permission checks.

Acceptance criteria:
- Deployment path is documented and reproducible.
- Sensitive operations are auditable and access-controlled.

## Questions To Resolve Next
1. Which exact Ubuntu, Debian, Windows Server, Windows 10, and Windows 11 ISOs are in scope for acceptance testing?
2. Should the worker remain on the web host for v1, or should template builds move to a separate build runner before broader use?
3. What AD signal should define faculty status: group membership, OU, or user attribute?
4. Do you want build job cancellation/retry in v1, or is status-only sufficient for the first release?

## Immediate Next Sprint Recommendation
1. Run live acceptance builds against the real Proxmox environment.
2. Turn the worker into a documented managed process.
3. Lock in the faculty-role source from AD before changing the template policy default.
