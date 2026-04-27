# Operations

This page is the deployment and troubleshooting runbook for the current Compose-based shape.

## Deployment Shape

Services:

- `migrate`: one-shot migration/check service.
- `web`: Django/Gunicorn app.
- `packer-worker`: background template build worker with Packer installed.

External dependencies:

- PostgreSQL database reachable from the Docker host.
- Active Directory domain controller(s).
- Proxmox API endpoint.
- NAS mount on the Ubuntu VM that runs Docker.
- Network access to ISO/software source URLs and HashiCorp Packer plugin downloads.

## Established Infrastructure Facts

- The NAS is mounted on the Ubuntu VM that runs Docker.
- The NAS mount is configured in `/etc/fstab`.
- Because the NAS is in `fstab`, the host should automatically remount it after reboot.
- Compose then bind-mounts the already-mounted host NAS path into the containers.
- The current worker runs as UID/GID `1000:1000` to match the writable NAS export.
- The NFS export has previously allowed host UID-based writes while squashing container root, so running the worker as root caused write failures.

## Host Paths

Recommended host paths:

- Jobs: `/srv/capstone/packer-jobs`
- NAS mount root: `/mnt/capstone-nas`
- Staged ISOs: `/mnt/capstone-nas/isos`
- Packer cache: `/mnt/capstone-nas/Templates/packer-cache`
- Job archives: `/mnt/capstone-nas/Templates/archives`
- User data: `/mnt/capstone-nas/UserData`

Container paths:

- Job workdir: `/var/lib/capstone/jobs`
- NAS root: `/mnt/capstone-nas`

Compose binds:

- `${PACKER_JOBS_HOST_PATH}` to `/var/lib/capstone/jobs`
- `${PACKER_NAS_HOST_PATH}` to `/mnt/capstone-nas`

## Pre-Deploy Checklist

On the Ubuntu Docker host:

```bash
test -f .env
test -d /mnt/capstone-nas
findmnt /mnt/capstone-nas
mkdir -p /srv/capstone/packer-jobs
mkdir -p /mnt/capstone-nas/isos
mkdir -p /mnt/capstone-nas/Templates/packer-cache
mkdir -p /mnt/capstone-nas/Templates/archives
mkdir -p /mnt/capstone-nas/UserData
```

Check write access as UID/GID `1000:1000`:

```bash
sudo -u '#1000' touch /mnt/capstone-nas/isos/.capstone-write-test
sudo -u '#1000' touch /mnt/capstone-nas/Templates/packer-cache/.capstone-write-test
sudo -u '#1000' touch /mnt/capstone-nas/Templates/archives/.capstone-write-test
sudo -u '#1000' touch /srv/capstone/packer-jobs/.capstone-write-test
```

If those fail, fix host/NFS permissions before starting template builds.

## Deploy Helper

Run from repo root on the deployment host:

```bash
scripts/deploy.sh
```

What it does:

1. Requires `.env`.
2. Sources `.env`.
3. Requires `DATABASE_URL`.
4. Rejects a `DATABASE_URL` that still points at Docker host `db`.
5. Creates `/srv/capstone/packer-jobs` or configured jobs path.
6. Verifies NAS mount path exists.
7. Creates cache, archive, and user data directories.
8. Runs `git fetch --all`.
9. Runs `git pull --ff-only`.
10. Builds Compose services.
11. Runs the one-shot migrate service.
12. Starts `web` and `packer-worker`.
13. Prints service status and recent worker logs.

## Manual Compose Commands

Build and start:

```bash
docker compose up --build -d web packer-worker
```

Run migrations/check:

```bash
docker compose run --rm migrate
```

View status:

```bash
docker compose ps
```

View worker logs:

```bash
docker compose logs --tail=200 packer-worker
```

View web logs:

```bash
docker compose logs --tail=200 web
```

Restart worker:

```bash
docker compose restart packer-worker
```

Rebuild after code changes:

```bash
docker compose build migrate web packer-worker
docker compose run --rm migrate
docker compose up -d web packer-worker
```

## Worker Runtime Checks

At worker startup, expect logs for:

- `Template build worker started`
- `worker check ok: packer_bin=...`
- `worker check ok: iso_tool=...`

If `TEMPLATE_BUILD_DEV_BYPASS=1`, startup reports that real Packer execution is skipped.

Production should not run with dev bypass enabled.

## Job Workspace Layout

Each queued job uses:

```text
TEMPLATE_BUILD_WORKDIR/
  job-<uuid>/
    request.json
    status.json
    generated/
    logs/
      packer.log
    results/
      preflight.json
      iso-stage.json
      software-results.json
      result.json
      error-summary.txt
```

Host path example:

```text
/srv/capstone/packer-jobs/job-<uuid>/
```

Container path example:

```text
/var/lib/capstone/jobs/job-<uuid>/
```

## Common Failure Modes

### Jobs Stay Queued

Likely causes:

- `packer-worker` is not running.
- Worker cannot connect to the database.
- Worker crashed during startup checks.
- Worker cannot claim jobs due to DB/migration mismatch.

Check:

```bash
docker compose ps
docker compose logs --tail=200 packer-worker
```

### Worker Cannot Rewrite Job Manifests

Symptoms:

- Job created by `web` but worker fails immediately.
- Logs mention permission denied under `/var/lib/capstone/jobs`.

Likely cause:

- `web` and `packer-worker` do not have compatible write permissions for `${PACKER_JOBS_HOST_PATH}`.

Fix:

- Ensure `${PACKER_JOBS_HOST_PATH}` is shared-writable.
- Consider host-side permissions repair for existing bad job dirs.
- Current code attempts `0777` dirs and `0666` files, but host/NFS behavior can still block writes.

### ISO Staging Fails Immediately

Likely causes:

- `PACKER_NAS_ISO_DIR` does not exist.
- Worker UID/GID cannot write the NAS export.
- NAS is not mounted on the host.
- Proxmox ISO storage is misconfigured.
- URL is not reachable from worker container.

Check:

```bash
findmnt /mnt/capstone-nas
docker compose exec packer-worker sh -lc 'id; ls -ld /mnt/capstone-nas /mnt/capstone-nas/isos'
docker compose logs --tail=200 packer-worker
```

### Packer Init Fails

Likely causes:

- No outbound network to download Packer plugin.
- Bad plugin source/version.
- Packer plugin cache path is not writable.

Check:

- `logs/packer.log`
- `results/error-summary.txt`
- `PACKER_PLUGIN_PATH`
- `PACKER_CACHE_DIR`

### Packer Validate Fails

Likely causes:

- HCL template incompatible with installed Packer Proxmox plugin.
- Wrong variable names.
- Bad Proxmox storage configuration.
- Missing required generated files.

Check:

- `logs/packer.log`
- `generated/template.pkr.hcl`
- `generated/template.auto.pkrvars.json`
- `results/preflight.json`

### Windows Build Hangs

Likely causes:

- Wrong image selector name/index.
- Wrong firmware profile for ISO.
- VirtIO ISO inaccessible or wrong.
- WinRM not enabled in guest.
- Administrator credentials rejected.
- Sysprep or guest agent install failure.

Check:

- `logs/packer.log`
- `results/software-results.json`
- `results/error-summary.txt`
- Proxmox console for the temporary build VM.

### VM Provisioning Fails

Likely causes:

- `PROXMOX_NODE` unset.
- Source template VMID missing or not a valid template.
- Proxmox token lacks clone/config/start permissions.
- Requested disk resize invalid.
- Static network payload invalid.

The API returns HTTP `502` with `Proxmox request failed: ...` for service exceptions.

## Stale Jobs

Worker startup runs `recover_stale_running_jobs()`.

A running job is stale when:

- `last_heartbeat_at` is older than `TEMPLATE_BUILD_STALE_AFTER_SECONDS`, or
- `last_heartbeat_at` is null and `started_at` is older than the stale cutoff.

Recovered jobs are marked:

- `status=failed`
- `stage=done`
- `exit_code=1` if not already set
- `error_summary=worker_restart_or_stale_claim`
- `result_payload.stale_recovered=true`

## Cleaning Old or Broken Job Directories

No automated retention policy exists yet.

Manual cleanup guidance:

- Do not remove a job directory for a currently running job.
- Prefer checking database status first.
- Failed/succeeded old job directories can be archived or deleted after you no longer need logs.
- Existing queued jobs from before permission fixes may need manual deletion or permissions repair.

Useful paths:

- Host jobs: `${PACKER_JOBS_HOST_PATH}/job-<uuid>/`
- Worker container jobs: `${TEMPLATE_BUILD_WORKDIR}/job-<uuid>/`

## Minimum Validation Before Merge/Deploy

From repo root:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

When touching API/auth/build code, also manually verify:

- Login success/failure.
- ISO inspect success/failure.
- VM start endpoint error handling for external API failures.
- Template build queue claim and live progress while the worker is running.
