# API

All API endpoints are implemented in `core/views.py` and registered in `capstoneDev/urls.py`.

## General Rules

- Login uses Django CSRF protection.
- JSON POSTs from the frontend include:
  - `Content-Type: application/json`
  - `X-CSRFToken`
  - `X-Requested-With: fetch`
- Authenticated endpoints use `@login_required`.
- Unauthenticated API calls generally receive Django's login redirect unless the view handles auth differently.
- External HTTP URL inspection accepts only `http` and `https`.
- Private URL hosts are allowed by default through `ALLOW_PRIVATE_TEMPLATE_ASSET_URLS=1`.
- When `ALLOW_PRIVATE_TEMPLATE_ASSET_URLS=0`, localhost, private, loopback, link-local, reserved, and multicast addresses are rejected.

## Endpoint Inventory

- `GET /`
- `GET /settings/`
- `GET /login/`
- `POST /login/`
- `POST /logout/`
- `POST /api/vm/start/`
- `GET /api/template/list/`
- `GET /api/iso/inspect`
- `GET /api/iso/inspect/`
- `GET /api/software/inspect`
- `GET /api/software/inspect/`
- `GET /api/iso/saved/`
- `GET /api/software/saved/`
- `POST /api/template/validate-software/`
- `POST /api/template/create/`
- `GET /api/template/builds/<job_uuid>/status/`

## Partial Page Navigation

`GET /` and `GET /settings/` return full HTML normally.

When `X-Requested-With` is `fetch` or `prefetch`, the views render the same template, extract named regions, and return JSON:

```json
{
  "title": "Capstone Home",
  "head": "<link ...>",
  "html": "<div ...>",
  "scripts": "<script ...>"
}
```

The frontend replaces `#app-content`, dynamic page head tags, and dynamic scripts.

## Login

### `GET /login/`

Renders the login page.

If the user is already authenticated, redirects to a safe `next` target or `LOGIN_REDIRECT_URL`.

### `POST /login/`

Expected headers:

- `Content-Type: application/json`
- `X-Requested-With: fetch`
- CSRF token

Request body:

```json
{
  "username": "jdoe",
  "password": "secret",
  "next": "/settings/"
}
```

Success:

- HTTP `200`

```json
{
  "ok": true,
  "redirect": "/settings/"
}
```

Failure:

- Invalid JSON: HTTP `400`
- Invalid credentials: HTTP `401`

```json
{
  "ok": false,
  "error": "Invalid username or password"
}
```

Redirect safety:

- Only same-host targets are accepted.
- Unsafe `next` values fall back to `/`.

## Logout

### `POST /logout/`

Requires login and CSRF.

Behavior:

- Calls Django logout.
- Redirects to `/login/`.

## ISO Inspection

### `GET /api/iso/inspect?url=<url>`

Requires login.

Behavior:

- Validates URL presence and scheme.
- Rejects private hosts only when `ALLOW_PRIVATE_TEMPLATE_ASSET_URLS=0`.
- Performs `HEAD`.
- Falls back to `GET` with `Range: bytes=0-0` when size is missing.
- Extracts filename from `Content-Disposition` or URL path.
- Requires filename to end in `.iso`.
- Saves or updates an `IsoSource` row for the user.

Success:

```json
{
  "ok": true,
  "final_url": "https://cdn.example/ubuntu.iso",
  "filename": "ubuntu.iso",
  "size_bytes": 123456,
  "content_type": "application/octet-stream",
  "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT"
}
```

Failures:

- Missing URL: HTTP `400`
- Non-http scheme: HTTP `400`
- Not a `.iso` filename: HTTP `400`
- HTTP metadata failure: HTTP `400`

## Software Inspection

### `GET /api/software/inspect?url=<url>`

Requires login.

Same behavior as ISO inspection, except it does not require `.iso`.

It saves or updates a `SoftwareSource` row for the user.

Success:

```json
{
  "ok": true,
  "final_url": "https://cdn.example/tool.exe",
  "filename": "tool.exe",
  "size_bytes": 123456,
  "content_type": "application/octet-stream",
  "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT"
}
```

## Saved Sources

### `GET /api/iso/saved/`

Requires login.

Returns up to 50 recent ISO sources for the current user.

Response:

```json
{
  "ok": true,
  "items": [
    {
      "url": "https://example/ubuntu.iso",
      "filename": "ubuntu.iso",
      "label": "",
      "size_bytes": 123456,
      "content_type": "application/octet-stream",
      "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT",
      "last_seen_at": "2026-04-27T13:00:00+00:00"
    }
  ]
}
```

### `GET /api/software/saved/`

Requires login.

Returns up to 50 recent software sources for the current user with the same shape as saved ISO sources.

## Software Validation

### `POST /api/template/validate-software/`

Requires login and CSRF.

Purpose:

- Normalizes Step 2 software selections.
- Validates package names.
- Inspects software URLs.
- Infers artifact type and install strategy.
- Applies target OS compatibility rules.
- Returns canonical software payload for template creation.

Request body:

```json
{
  "build_profile": "ubuntu_autoinstall",
  "target_os": "linux",
  "software_items": [
    {
      "kind": "url",
      "label": "Example installer",
      "url": "https://example/tool.deb",
      "artifact_type": "",
      "install_strategy": "",
      "silent_args": ""
    },
    {
      "kind": "package",
      "label": "nginx"
    }
  ],
  "services": {
    "qemu_guest": true,
    "docker": false,
    "devtools": false
  }
}
```

Backward-compatible keys accepted:

- `software_urls`
- `custom_packages`

Package rules:

- Package names must match `^[a-z0-9][a-z0-9+.-]{0,63}$`.
- Package-manager packages are supported for Linux targets.
- Package-manager packages are rejected for Windows targets.

Artifact inference:

- Windows native installers: `exe`, `msi`, `msix`
- Windows scripts: `ps1`, `bat`, `cmd`
- Linux packages: `deb`, `rpm`, `apk`
- Archives: `zip`, `tar`
- Linux scripts/binaries: `sh`, `run`, `bin`
- Unknown values are allowed with warnings in some paths.

Install strategy inference:

- `package_manager`
- `native_installer`
- `archive`
- `script`
- `custom_command`

Windows native installers get default silent args `/quiet /norestart` when args are missing.

Response:

```json
{
  "ok": true,
  "valid": true,
  "errors": [],
  "warnings": [],
  "normalized": {
    "target_os": "linux",
    "software_urls": ["https://example/tool.deb"],
    "software_items": [
      {
        "id": "software-1",
        "kind": "url",
        "url": "https://example/tool.deb",
        "label": "tool.deb",
        "filename": "tool.deb",
        "size_bytes": 123456,
        "content_type": "application/octet-stream",
        "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "artifact_type": "deb",
        "install_strategy": "package_manager",
        "silent_args": ""
      }
    ],
    "custom_packages": ["nginx"],
    "services": {
      "qemu_guest": true,
      "docker": false,
      "devtools": false
    }
  }
}
```

## Template Creation

### `POST /api/template/create/`

Requires login and CSRF.

Authorization:

- If `TEMPLATE_CREATION_POLICY=faculty_only`, `request.user.is_staff` must be true.
- Otherwise returns HTTP `403`.

Request body:

```json
{
  "template_name": "ubuntu-24.04-base",
  "build_profile": "ubuntu_autoinstall",
  "target_os": "linux",
  "iso_url": "https://example/ubuntu.iso",
  "hardware": {
    "cpu": 2,
    "ram_gb": 4,
    "disk_gb": 32
  },
  "network": {
    "bridge": "vmbr0",
    "vlan": 20,
    "ipv4_mode": "dhcp"
  },
  "software_items": [],
  "services": {
    "qemu_guest": true,
    "docker": false,
    "devtools": false
  },
  "linux": {
    "ssh_timeout": "45m"
  },
  "ansible": {}
}
```

Windows request body adds:

```json
{
  "build_profile": "windows_unattend",
  "target_os": "windows",
  "windows": {
    "admin_username": "Administrator",
    "admin_password": "secret",
    "image_selector_type": "image_name",
    "image_selector_value": "Windows Server 2022 SERVERSTANDARD",
    "virtio_iso_url": "https://example/virtio-win.iso",
    "firmware_profile": "uefi_tpm",
    "winrm_port": 5985,
    "winrm_use_ssl": false,
    "winrm_timeout": "2h"
  }
}
```

Validation rules:

- `build_profile` is required and must be one of the supported profiles.
- `target_os`, when supplied, must match the profile.
- `template_name` is required.
- `iso_url` is required and must inspect as an ISO.
- Software validation must pass.
- Hardware is clamped:
  - CPU: `1..64`, default `2`
  - RAM GB: `1..512`, default `4`
  - Disk GB: `8..4096`, default `32`
- `network.bridge` is required.
- Template networking must be DHCP-ready only.
- Any static template networking values cause HTTP `400`.
- Windows builds require all Windows fields above.
- Windows `virtio_iso_url` is inspected as an ISO.
- Template VMID requires a synced `DirectoryProfile.ad_rid`.

Success:

- HTTP `202`

```json
{
  "ok": true,
  "template": {
    "id": 1,
    "name": "ubuntu-24.04-base",
    "vmid": "1536001",
    "target_os": "linux",
    "build_profile": "ubuntu_autoinstall"
  },
  "job": {
    "id": "94c4d723-4b37-46ef-a4a1-03a228a9b7b7",
    "status": "queued",
    "stage": "queued"
  },
  "warnings": [],
  "normalized": {}
}
```

Important behavior:

- This endpoint queues the job.
- It does not run Packer inline.
- It writes initial `request.json` and `status.json` only.
- Generated Packer files are written later by the worker.
- Request manifests redact keys matching password, secret, or token.

Failures:

- Not faculty under faculty-only policy: HTTP `403`
- Invalid JSON: HTTP `400`
- Missing build profile/name/ISO: HTTP `400`
- ISO validation failure: HTTP `400`
- Software validation failure: HTTP `400`
- Static template networking: HTTP `400`
- Missing directory profile/RID: HTTP `400`
- Failed queue/write: HTTP `500`, with the new `TemplateDefinition` deleted.

## Template List

### `GET /api/template/list/`

Requires login.

Returns completed templates owned by the caller. A template is considered ready when `last_job.status == succeeded`.

Response:

```json
{
  "ok": true,
  "items": [
    {
      "id": 1,
      "name": "ubuntu-template",
      "vmid": "1536001",
      "target_os": "linux",
      "build_profile": "ubuntu_autoinstall",
      "hardware": {
        "cpu": 2,
        "ram_gb": 4,
        "disk_gb": 32
      },
      "network": {
        "bridge": "vmbr0",
        "vlan": 20,
        "ipv4_mode": "dhcp"
      }
    }
  ]
}
```

## VM Provisioning

### `POST /api/vm/start/`

Requires login and CSRF.

Request body:

```json
{
  "template_id": 1,
  "name": "student-lab-01",
  "hardware": {
    "cpu": 4,
    "ram_gb": 8,
    "disk_gb": 64
  },
  "network": {
    "bridge": "vmbr0",
    "vlan": 20,
    "ipv4_mode": "static",
    "static_ip": "10.0.20.50/24",
    "static_gateway": "10.0.20.1",
    "static_dns": ["10.0.20.10", "10.0.20.11"]
  }
}
```

Validation rules:

- `template_id` must be a positive integer.
- Template must belong to the caller.
- Template must have a succeeded last build.
- VM name is required.
- Hardware is clamped:
  - CPU: `1..64`, default `2`
  - RAM GB: `1..512`, default `4`
  - Disk GB: `8..4096`, default `32`
- Requested disk size must be at least the template source disk size.
- Network bridge is required.
- VLAN is optional and clamped to `1..4094`.
- IPv4 mode must be `dhcp` or `static`.
- Static mode requires valid CIDR `static_ip`.
- Static mode requires valid IP `static_gateway`.
- Static DNS values, when supplied, must be valid IP addresses.
- DHCP mode clears static fields.

Success:

- HTTP `201`

```json
{
  "ok": true,
  "vm": {
    "id": 1,
    "name": "student-lab-01",
    "vmid": 2400,
    "node": "pve",
    "status": "running",
    "task_upid": "UPID:...",
    "error": null,
    "hardware": {
      "cpu": 4,
      "ram_gb": 8,
      "disk_gb": 64
    },
    "network": {
      "bridge": "vmbr0",
      "vlan": 20,
      "ipv4_mode": "static",
      "static_ip": "10.0.20.50/24",
      "static_gateway": "10.0.20.1",
      "static_dns": ["10.0.20.10", "10.0.20.11"]
    },
    "created_at": "2026-04-27T13:00:00+00:00",
    "provisioned_at": "2026-04-27T13:01:00+00:00",
    "started_at": "2026-04-27T13:01:00+00:00",
    "template": {
      "id": 1,
      "name": "ubuntu-template",
      "vmid": "1536001",
      "target_os": "linux",
      "build_profile": "ubuntu_autoinstall",
      "hardware": {},
      "network": {}
    }
  }
}
```

Failures:

- Missing/invalid template ID: HTTP `400`
- Template not found or not owned by user: HTTP `404`
- Payload validation failures: HTTP `400`
- Proxmox/client/service exception: HTTP `502`

## Build Status

### `GET /api/template/builds/<job_uuid>/status/`

Requires login.

Only the job owner can view status. Other users receive HTTP `404`.

Response:

```json
{
  "ok": true,
  "job": {
    "id": "94c4d723-4b37-46ef-a4a1-03a228a9b7b7",
    "status": "running",
    "stage": "assets",
    "error": null,
    "exit_code": null,
    "queued_at": "2026-04-27T13:00:00+00:00",
    "started_at": "2026-04-27T13:00:05+00:00",
    "finished_at": null,
    "template": {
      "id": 1,
      "name": "ubuntu-template",
      "vmid": "1536001",
      "target_os": "linux",
      "build_profile": "ubuntu_autoinstall"
    },
    "result": {
      "software_results": [],
      "preflight": [],
      "staged_isos": [],
      "iso_stage_progress": null,
      "generated_artifacts": [],
      "machine_readable_events": [],
      "log_available": false,
      "archive_available": false,
      "dev_bypass": false,
      "execution_mode": null,
      "summary": null,
      "build_profile": "ubuntu_autoinstall",
      "firmware_profile": null,
      "image_selector": {
        "type": null,
        "value": null
      },
      "guest_networking": "dhcp"
    }
  }
}
```

Status values:

- `queued`
- `running`
- `succeeded`
- `failed`
- `canceled`

Stage values:

- `queued`
- `preflight`
- `assets`
- `init`
- `validate`
- `build`
- `sealing`
- `postprocess`
- `done`

The status payload intentionally does not expose raw workspace or log paths.
