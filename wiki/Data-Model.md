# Data Model

The current app uses Django models in `core/models.py`. Migrations live under `core/migrations/`.

## Models

### `IsoSource`

Purpose:

- Per-user history of inspected ISO URLs.
- Used by the Create Template modal's saved ISO selector.

Fields:

- `user`: Django auth user, cascade delete.
- `url`: URL, max length 512.
- `filename`: optional filename.
- `content_type`: optional content type.
- `size_bytes`: optional size.
- `last_modified`: optional HTTP last-modified value.
- `label`: optional display label.
- `created_at`: insert timestamp.
- `last_seen_at`: updated on every record update.

Indexes/constraints:

- Index on `user`, `url`.
- Unique together: `user`, `url`.

### `SoftwareSource`

Purpose:

- Per-user history of inspected software URLs.
- Used by the Create Template modal's saved software list.

Fields mirror `IsoSource`:

- `user`
- `url`
- `filename`
- `content_type`
- `size_bytes`
- `last_modified`
- `label`
- `created_at`
- `last_seen_at`

Indexes/constraints:

- Index on `user`, `url`.
- Unique together: `user`, `url`.

### `DirectoryProfile`

Purpose:

- Stores AD-derived identity and role metadata for a Django user.
- Provides the AD RID used by current template VMID allocation.
- Feeds settings page account/access display.

Role values:

- `unknown`
- `student`
- `faculty`

Fields:

- `user`: one-to-one Django auth user, related name `directory_profile`.
- `ad_object_sid`: unique SID string.
- `ad_rid`: unique RID parsed from the SID.
- `display_name`
- `distinguished_name`
- `user_principal_name`
- `department`
- `company`
- `directory_role`
- `raw_attributes`: JSON copy of normalized AD attributes.
- `created_at`
- `updated_at`

Indexes:

- `directory_role`, `updated_at`

Notes:

- Missing `DirectoryProfile` prevents template creation because VMID allocation requires `ad_rid`.
- Faculty role currently maps to `user.is_staff=True` during AD sync.

### `TemplateDefinition`

Purpose:

- Persistent source of truth for a template requested by a user.
- Stores normalized payload snapshots needed for future provisioning and history.

Target OS values:

- `linux`
- `windows`

Fields:

- `owner`: Django auth user, related name `template_definitions`.
- `template_name`: display/name input from user.
- `template_vmid`: Proxmox VMID for the template VM.
- `build_profile`: one of the supported Packer profiles.
- `target_os`: `linux` or `windows`.
- `iso_url`: final inspected installer ISO URL.
- `iso_filename`
- `iso_size_bytes`
- `normalized_payload`: JSON from software validation plus profile/target OS.
- `hardware`: JSON snapshot.
- `network`: JSON snapshot.
- `windows_options`: JSON snapshot for Windows-specific fields.
- `ansible_options`: JSON metadata, currently stored but not executed.
- `last_job`: nullable FK to latest `TemplateBuildJob`.
- `created_at`
- `updated_at`

Indexes/constraints:

- Index on `owner`, `template_vmid`.
- Index on `target_os`, `updated_at`.
- Unique together: `owner`, `template_vmid`.

Current VMID behavior:

- Prefix is `DirectoryProfile.ad_rid`.
- Suffix is a three-digit per-owner sequence.
- Example: `1536001`.

### `TemplateBuildJob`

Purpose:

- Async job record consumed by `packer-worker`.
- Tracks queue state, stage, workspace paths, payload snapshot, result summary, and errors.

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
- `postprocess`
- `sealing`
- `done`

Fields:

- `uuid`: public job ID.
- `owner`: Django auth user, related name `template_build_jobs`.
- `template_definition`: FK to `TemplateDefinition`, related name `build_jobs`.
- `status`
- `stage`
- `payload_snapshot`: JSON build request snapshot.
- `result_payload`: JSON result/status summary.
- `workspace_path`: internal workspace path.
- `log_path`: internal Packer log path.
- `packer_template_path`: generated HCL path.
- `exit_code`
- `error_summary`
- `queued_at`
- `started_at`
- `last_heartbeat_at`
- `finished_at`
- `created_at`
- `updated_at`

Indexes:

- `status`, `queued_at`
- `owner`, `created_at`

Notes:

- Status API intentionally does not expose raw filesystem paths.
- `workspace_path`, `log_path`, and `packer_template_path` are still stored for backend/admin use.
- `canceled` is modeled but no cancel endpoint/UI exists yet.

### `VirtualMachine`

Purpose:

- Persistent record of VMs provisioned from completed templates.

Status values:

- `provisioning`
- `running`
- `failed`

Fields:

- `owner`: Django auth user, related name `virtual_machines`.
- `template_definition`: source template, related name `virtual_machines`.
- `proxmox_vmid`: unique destination VMID allocated by Proxmox.
- `name`
- `node`
- `hardware`: JSON requested/applied hardware.
- `network`: JSON requested/applied network.
- `status`
- `task_upid`: latest Proxmox task UPID seen.
- `last_error`: failure detail when provisioning fails.
- `provisioned_at`
- `started_at`
- `created_at`
- `updated_at`

Indexes:

- `owner`, `created_at`
- `status`, `updated_at`

## Migration History

- `0001_initial`
  - Creates `IsoSource`.
  - Creates `SoftwareSource`.
- `0002_templatebuildjob_templatedefinition_and_more`
  - Creates `TemplateBuildJob`.
  - Creates `TemplateDefinition`.
  - Adds indexes and unique template owner/VMID constraint.
- `0003_templatedefinition_build_profile`
  - Adds `TemplateDefinition.build_profile`.
- `0004_templatebuildjob_last_heartbeat_at`
  - Adds heartbeat timestamp.
- `0005_directoryprofile`
  - Adds `DirectoryProfile`.
- `0006_virtualmachine_and_more`
  - Adds `VirtualMachine`.

## Admin Registration

Registered in `core/admin.py`:

- `IsoSource`
- `SoftwareSource`
- `TemplateDefinition`
- `TemplateBuildJob`
- `VirtualMachine`

`DirectoryProfile` is not currently registered in admin.

## Legacy Database Folder

The `database/` folder contains a separate `Capstone2026USERS.db` and `schemaCapstone2026.sql` describing a simple `users` table. That appears to be legacy/reference material and is not the current Django application database model. Current Django persistence is defined by `core/models.py` and migrations.
