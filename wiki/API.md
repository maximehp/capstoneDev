# API

## Current Endpoints
- `POST /login/`
- `POST /api/vm/start/`
- `GET /api/iso/inspect`
- `GET /api/software/inspect`
- `GET /api/iso/saved/`
- `GET /api/software/saved/`
- `POST /api/template/validate-software/`
- `POST /api/template/create/`
- `GET /api/template/builds/<job_uuid>/status/`

## Expected Behaviors
- `POST /login/` authenticates against AD and establishes a Django session.
- `POST /api/vm/start/` clones from a Proxmox template and starts a VM.
- `GET /api/iso/inspect` validates a URL and returns basic ISO metadata.
- `GET /api/software/inspect` validates a software download URL and returns metadata.
- `GET /api/iso/saved/` returns up to 50 saved ISO URLs for the logged-in user.
- `GET /api/software/saved/` returns up to 50 saved software URLs for the logged-in user.
- `POST /api/template/validate-software/` validates Step 2 software/services/package inputs and returns a normalized payload for template creation.
- `POST /api/template/create/` validates payload, creates a `TemplateDefinition`, and enqueues an async `TemplateBuildJob`.
- `GET /api/template/builds/<job_uuid>/status/` returns build job lifecycle status and structured build result payload.

## Validation Contract
`POST /api/template/validate-software/` request body:
- `build_profile`: `ubuntu_autoinstall`, `debian_preseed`, or `windows_unattend`
- `target_os`: `linux` or `windows`
- `software_items`: array of selected items
  - `kind`: `url` or `package`
  - `label`: display name
  - `url`: when kind is `url`
  - `artifact_type`: inferred/provided file type
  - `install_strategy`: inferred/provided strategy
  - `silent_args`: optional args for installer execution
- backward-compat keys are still accepted:
  - `software_urls`
  - `custom_packages`
- `services`: object with boolean flags
  - `qemu_guest`
  - `docker`
  - `devtools`

Response body:
- `ok`: request processing status
- `valid`: `true` if no validation errors
- `errors`: list of validation errors
- `warnings`: list of non-blocking issues
- `normalized`: canonicalized data for downstream provisioning
  - `build_profile`
  - `target_os`
  - `software_urls`
  - `software_items` (URL/package + metadata + strategy + args)
  - `custom_packages`
  - `services`

## Template Create Contract
`POST /api/template/create/` request body:
- `template_name`
- `build_profile`
- `target_os`
- `iso_url`
- `hardware`
  - `cpu`
  - `ram_gb`
  - `disk_gb`
- `network`
  - `bridge`
  - `vlan`
  - `ipv4_mode` must remain `dhcp`
- `software_items`
- `software_urls`
- `custom_packages`
- `services`
- `linux`
  - `ssh_timeout`
- `windows` for `windows_unattend`
  - `admin_username`
  - `admin_password`
  - `image_selector_type`
  - `image_selector_value`
  - `virtio_iso_url`
  - `firmware_profile` (`bios_legacy` or `uefi_tpm`)
  - `winrm_port`
  - `winrm_use_ssl`
  - `winrm_timeout`
- `ansible` optional metadata only

Current rules:
- `build_profile` is required.
- `target_os` must match the selected profile.
- Static template networking is rejected.
- Windows builds require the full Windows block above.
- ISO URLs and VirtIO URLs are inspected before job creation.
- VMID is assigned as `"100" + user.id`.

Successful create response:
- HTTP `202`
- `template`
  - `id`
  - `name`
  - `vmid`
  - `target_os`
  - `build_profile`
- `job`
  - `id`
  - `status`
  - `stage`
- `warnings`
- `normalized`

Important behavior:
- `POST /api/template/create/` does not create the generated Packer files inline.
- Those files are created later by the background worker when it executes the queued job.

## Build Status Contract
`GET /api/template/builds/<job_uuid>/status/` response body:
- `job.id`
- `job.status`
- `job.stage`
- `job.error`
- `job.exit_code`
- `job.template`
  - `id`
  - `name`
  - `vmid`
  - `target_os`
  - `build_profile`
- `job.result`
  - `software_results`
  - `preflight`
  - `staged_isos`
  - `iso_stage_progress`
  - `generated_artifacts`
  - `image_selector`
  - `firmware_profile`
  - `guest_networking`

Current build-stage semantics:
- `queued`: request persisted but not yet claimed by worker
- `preflight`: runtime/path/storage validation
- `assets`: NAS ISO staging and transfer progress
- `init`: `packer init`
- `validate`: `packer validate`
- `build`: live Packer build/install stage
- `sealing`: late guest finalization/signoff
- `postprocess`: final worker wrap-up
- `done`: terminal state

`job.result.staged_isos` items currently include:
- `role`
- `filename`
- `storage_pool`
- `iso_file`
- `local_path`
- `final_url`
- `size_bytes`
- `reused`

`job.result.iso_stage_progress` currently includes:
- `status`
- `role`
- `filename`
- `iso_file`
- `downloaded_bytes`
- `expected_bytes`
- `percent`
- `speed_bytes_per_sec`
- `local_path`
- `final_url`

## Planned Endpoints
- `GET /api/template/list/` for listing templates.
- `POST /api/vm/create/` for user-provisioned VMs with configuration.

## Notes
- Requests from the UI use `X-Requested-With: fetch` or `prefetch` for partial navigation.
- Software validation remains a preflight/normalization step.
- Packer execution happens in the worker, not in the create request.
- Windows native installer items currently get backend default silent args (`/quiet /norestart`) when args are missing.
