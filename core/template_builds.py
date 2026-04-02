import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape as xml_escape

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import TemplateBuildJob, TemplateDefinition
from .packer_profiles import (
    BUILD_PROFILE_DEBIAN_PRESEED,
    BUILD_PROFILE_UBUNTU_AUTOINSTALL,
    BUILD_PROFILE_WINDOWS_UNATTEND,
    WINDOWS_FIRMWARE_BIOS_LEGACY,
    WINDOWS_FIRMWARE_UEFI_TPM,
)


_RESULT_MARKER_RE = re.compile(r"CAPSTONE_ITEM_RESULT\|([^|]+)\|([^|]+)\|([^|]+)\|(.*)")
_STAGE_MARKER_RE = re.compile(r"CAPSTONE_STAGE\|([^|]+)")
_SENSITIVE_KEY_RE = re.compile(r"(password|secret|token)", re.IGNORECASE)
_FIXED_LINUX_USERNAME = "capstonebuild"
_FIXED_LINUX_PASSWORD = "CapstoneBuild123!"
_FIXED_LINUX_PASSWORD_HASH = "$6$rounds=4096$capstone$0ylvD6QBGzb62LF8A3BnQUwpsOSJyYwcmBHQYaWV7kngakdUSHh3D1ynjUTduVdJN9WewtG/XAIN5e8wZsMIf0"


def template_creation_allowed(user) -> bool:
    policy = getattr(settings, "TEMPLATE_CREATION_POLICY", "faculty_only")
    if policy == "faculty_only":
        return bool(getattr(user, "is_staff", False))
    return True


def enqueue_template_build(template_definition: TemplateDefinition, payload_snapshot: dict) -> TemplateBuildJob:
    job = TemplateBuildJob.objects.create(
        owner=template_definition.owner,
        template_definition=template_definition,
        payload_snapshot=payload_snapshot,
        status=TemplateBuildJob.STATUS_QUEUED,
        stage=TemplateBuildJob.STAGE_QUEUED,
    )
    workspace = _job_workspace(job.uuid)
    paths = _ensure_job_workspace(workspace)
    job.workspace_path = str(workspace)
    job.log_path = str(paths["packer_log"])
    job.save(update_fields=["workspace_path", "log_path", "updated_at"])
    _write_job_request_manifest(job, payload_snapshot)
    _write_job_status_manifest(job)
    template_definition.last_job = job
    template_definition.save(update_fields=["last_job", "updated_at"])
    return job


def claim_next_queued_job() -> TemplateBuildJob | None:
    with transaction.atomic():
        job = (
            TemplateBuildJob.objects
            .select_for_update(skip_locked=True)
            .filter(status=TemplateBuildJob.STATUS_QUEUED)
            .order_by("queued_at", "id")
            .first()
        )
        if not job:
            return None

        job.status = TemplateBuildJob.STATUS_RUNNING
        job.stage = TemplateBuildJob.STAGE_PREFLIGHT
        job.started_at = timezone.now()
        job.last_heartbeat_at = job.started_at
        job.error_summary = ""
        job.exit_code = None
        job.save(
            update_fields=[
                "status",
                "stage",
                "started_at",
                "last_heartbeat_at",
                "error_summary",
                "exit_code",
                "updated_at",
            ]
        )
        _write_job_status_manifest(job)
        return job


def build_job_api_payload(job: TemplateBuildJob) -> dict:
    result_payload = job.result_payload if isinstance(job.result_payload, dict) else {}
    payload_snapshot = job.payload_snapshot if isinstance(job.payload_snapshot, dict) else {}
    windows = payload_snapshot.get("windows") if isinstance(payload_snapshot.get("windows"), dict) else {}
    image_selector = {
        "type": windows.get("image_selector_type"),
        "value": windows.get("image_selector_value"),
    }
    return {
        "id": str(job.uuid),
        "status": job.status,
        "stage": job.stage,
        "error": job.error_summary or None,
        "exit_code": job.exit_code,
        "queued_at": job.queued_at.isoformat() if job.queued_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "template": {
            "id": job.template_definition_id,
            "name": job.template_definition.template_name,
            "vmid": job.template_definition.template_vmid,
            "target_os": job.template_definition.target_os,
            "build_profile": job.template_definition.build_profile,
        },
        "result": {
            "software_results": result_payload.get("software_results", []),
            "preflight": result_payload.get("preflight", []),
            "generated_artifacts": result_payload.get("generated_artifacts", []),
            "machine_readable_events": result_payload.get("machine_readable_events", []),
            "log_available": bool(result_payload.get("log_available")),
            "archive_available": bool(result_payload.get("archive_available")),
            "dev_bypass": bool(result_payload.get("dev_bypass")),
            "execution_mode": result_payload.get("execution_mode"),
            "summary": result_payload.get("summary"),
            "build_profile": payload_snapshot.get("build_profile") or job.template_definition.build_profile,
            "firmware_profile": windows.get("firmware_profile"),
            "image_selector": image_selector,
            "guest_networking": payload_snapshot.get("guest_networking") or "dhcp",
        },
    }


def _job_workspace(job_uuid) -> Path:
    return Path(settings.TEMPLATE_BUILD_WORKDIR) / f"job-{job_uuid}"


def _ensure_job_workspace(workspace: Path) -> dict[str, Path]:
    generated_dir = workspace / "generated"
    logs_dir = workspace / "logs"
    results_dir = workspace / "results"
    for path in [workspace, generated_dir, logs_dir, results_dir]:
        path.mkdir(parents=True, exist_ok=True)
    return {
        "workspace": workspace,
        "generated": generated_dir,
        "logs": logs_dir,
        "results": results_dir,
        "request": workspace / "request.json",
        "status": workspace / "status.json",
        "packer_log": logs_dir / "packer.log",
        "result": results_dir / "result.json",
        "software_results": results_dir / "software-results.json",
        "preflight": results_dir / "preflight.json",
        "error_summary": results_dir / "error-summary.txt",
    }


def _write_json(path: Path, payload: dict | list):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _redact_value(value: str) -> str:
    return "[REDACTED]" if value else value


def _redact_payload(payload):
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            if _SENSITIVE_KEY_RE.search(str(key)):
                out[key] = _redact_value(str(value)) if value not in {None, ""} else value
            else:
                out[key] = _redact_payload(value)
        return out
    if isinstance(payload, list):
        return [_redact_payload(item) for item in payload]
    return payload


def _artifact_record(kind: str, path: Path, workspace: Path) -> dict:
    directory = path.parent.relative_to(workspace).as_posix() if path.parent != workspace else "."
    return {
        "kind": kind,
        "name": path.name,
        "directory": directory,
        "available": path.exists(),
    }


def _write_job_request_manifest(job: TemplateBuildJob, payload_snapshot: dict):
    workspace = _job_workspace(job.uuid)
    paths = _ensure_job_workspace(workspace)
    payload = {
        "job_id": str(job.uuid),
        "template_id": job.template_definition_id,
        "owner_id": job.owner_id,
        "build_profile": job.template_definition.build_profile,
        "target_os": job.template_definition.target_os,
        "queued_at": job.queued_at.isoformat() if job.queued_at else None,
        "request": _redact_payload(payload_snapshot),
    }
    _write_json(paths["request"], payload)


def _write_job_status_manifest(job: TemplateBuildJob):
    workspace = _job_workspace(job.uuid)
    paths = _ensure_job_workspace(workspace)
    payload = build_job_api_payload(job)
    _write_json(paths["status"], {"job": payload, "updated_at": timezone.now().isoformat()})


def _touch_job_heartbeat(job: TemplateBuildJob):
    job.last_heartbeat_at = timezone.now()
    job.save(update_fields=["last_heartbeat_at", "updated_at"])


def recover_stale_running_jobs() -> int:
    cutoff = timezone.now() - timedelta(seconds=max(1, settings.TEMPLATE_BUILD_STALE_AFTER_SECONDS))
    stale_jobs = (
        TemplateBuildJob.objects
        .select_related("template_definition")
        .filter(status=TemplateBuildJob.STATUS_RUNNING)
        .filter(
            Q(last_heartbeat_at__lt=cutoff) |
            Q(last_heartbeat_at__isnull=True, started_at__lt=cutoff)
        )
    )
    recovered = 0
    for job in stale_jobs:
        job.status = TemplateBuildJob.STATUS_FAILED
        job.stage = TemplateBuildJob.STAGE_DONE
        job.finished_at = timezone.now()
        job.exit_code = 1 if job.exit_code is None else job.exit_code
        job.error_summary = "worker_restart_or_stale_claim"
        result_payload = job.result_payload if isinstance(job.result_payload, dict) else {}
        result_payload["stale_recovered"] = True
        job.result_payload = result_payload
        job.save(
            update_fields=[
                "status",
                "stage",
                "finished_at",
                "exit_code",
                "error_summary",
                "result_payload",
                "updated_at",
            ]
        )
        workspace = _job_workspace(job.uuid)
        paths = _ensure_job_workspace(workspace)
        paths["error_summary"].write_text(job.error_summary, encoding="utf-8")
        _write_json(paths["result"], {"job": build_job_api_payload(job)})
        _write_job_status_manifest(job)
        recovered += 1
    return recovered


def ensure_worker_runtime_ready() -> list[dict]:
    Path(settings.TEMPLATE_BUILD_WORKDIR).mkdir(parents=True, exist_ok=True)
    Path(settings.PACKER_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    checks = []
    if getattr(settings, "TEMPLATE_BUILD_DEV_BYPASS", False):
        checks.append(
            {
                "check": "packer_bin",
                "ok": True,
                "skipped": True,
                "reason": "dev_bypass",
                "value": str(getattr(settings, "PACKER_BIN", "packer") or "packer"),
            }
        )
        checks.append(
            {
                "check": "iso_tool",
                "ok": True,
                "skipped": True,
                "reason": "dev_bypass",
                "value": str(getattr(settings, "PACKER_ISO_TOOL", "") or ""),
            }
        )
        return checks

    packer_bin = str(getattr(settings, "PACKER_BIN", "packer") or "packer")
    resolved_packer = shutil.which(packer_bin) if Path(packer_bin).name == packer_bin else str(Path(packer_bin))
    if not resolved_packer or (Path(packer_bin).name != packer_bin and not Path(resolved_packer).exists()):
        raise RuntimeError(f"Packer binary not found: {packer_bin}")
    checks.append({"check": "packer_bin", "ok": True, "value": resolved_packer})

    iso_tool = _detect_iso_tool()
    if not iso_tool:
        raise RuntimeError("No ISO authoring tool found. Configure PACKER_ISO_TOOL or install oscdimg/xorriso/mkisofs.")
    checks.append({"check": "iso_tool", "ok": True, "value": iso_tool})
    return checks


def run_build_job(job: TemplateBuildJob) -> TemplateBuildJob:
    job = TemplateBuildJob.objects.select_related("template_definition", "owner").get(pk=job.pk)

    workspace = _job_workspace(job.uuid)
    paths = _ensure_job_workspace(workspace)
    log_path = paths["packer_log"]

    payload = job.payload_snapshot if isinstance(job.payload_snapshot, dict) else {}
    build_profile = str(payload.get("build_profile") or job.template_definition.build_profile or "").strip().lower()
    target_os = str(payload.get("target_os") or "").lower()

    software_results: list[dict] = []
    preflight_results: list[dict] = []
    generated_artifacts: list[dict] = []
    machine_readable_events: list[dict] = []
    archive_available = False
    redaction_values = _build_redaction_values(payload)

    def on_output(line: str):
        parsed = _parse_result_marker(line)
        if parsed:
            software_results.append(parsed)
        stage_name = _parse_stage_marker(line)
        if stage_name == "sealing":
            _set_stage(job, TemplateBuildJob.STAGE_SEALING)
        machine_event = _parse_machine_readable_event(line)
        if machine_event:
            machine_readable_events.append(machine_event)

    if getattr(settings, "TEMPLATE_BUILD_DEV_BYPASS", False):
        return _run_dev_bypass_job(
            job=job,
            paths=paths,
            payload=payload,
            software_results=software_results,
            machine_readable_events=machine_readable_events,
        )

    try:
        template_file = _resolve_template_file(build_profile, payload)
        generated_template_file = paths["generated"] / "template.pkr.hcl"
        generated_template_file.write_text(template_file.read_text(encoding="utf-8"), encoding="utf-8")

        job.workspace_path = str(workspace)
        job.log_path = str(log_path)
        job.packer_template_path = str(generated_template_file)
        job.save(update_fields=["workspace_path", "log_path", "packer_template_path", "updated_at"])
        _write_job_status_manifest(job)

        with log_path.open("a", encoding="utf-8") as log_fp:
            _set_stage(job, TemplateBuildJob.STAGE_PREFLIGHT)
            preflight_results = _run_preflight(build_profile=build_profile, payload=payload, log_fp=log_fp)
            _write_json(paths["preflight"], {"checks": preflight_results})

            profile_artifacts, profile_context = _write_profile_artifacts(
                build_profile=build_profile,
                payload=payload,
                workspace=paths["generated"],
            )
            generated_artifacts = profile_artifacts
            bootstrap_script = _write_bootstrap_script(
                build_profile=build_profile,
                target_os=target_os,
                payload=payload,
                workspace=paths["generated"],
            )
            generated_artifacts.append(_artifact_record("bootstrap_script", bootstrap_script, workspace))

            vars_file = _write_packer_vars_file(
                build_profile=build_profile,
                target_os=target_os,
                payload=payload,
                workspace=paths["generated"],
                bootstrap_script=bootstrap_script,
                profile_context=profile_context,
            )
            generated_artifacts.append(_artifact_record("packer_vars", vars_file, workspace))

            _set_stage(job, TemplateBuildJob.STAGE_INIT)
            _run_command(
                [settings.PACKER_BIN, "init", generated_template_file.name],
                cwd=paths["generated"],
                timeout_sec=settings.TEMPLATE_BUILD_MAX_TIMEOUT_SEC,
                log_fp=log_fp,
                on_output=on_output,
                heartbeat_cb=lambda: _touch_job_heartbeat(job),
                redaction_values=redaction_values,
            )

            _set_stage(job, TemplateBuildJob.STAGE_VALIDATE)
            _run_command(
                [settings.PACKER_BIN, "validate", "-var-file", vars_file.name, generated_template_file.name],
                cwd=paths["generated"],
                timeout_sec=settings.TEMPLATE_BUILD_MAX_TIMEOUT_SEC,
                log_fp=log_fp,
                on_output=on_output,
                heartbeat_cb=lambda: _touch_job_heartbeat(job),
                redaction_values=redaction_values,
            )

            _set_stage(job, TemplateBuildJob.STAGE_BUILD)
            _run_command(
                [
                    settings.PACKER_BIN,
                    "build",
                    "-machine-readable",
                    "-color=false",
                    "-var-file",
                    vars_file.name,
                    generated_template_file.name,
                ],
                cwd=paths["generated"],
                timeout_sec=settings.TEMPLATE_BUILD_MAX_TIMEOUT_SEC,
                log_fp=log_fp,
                on_output=on_output,
                heartbeat_cb=lambda: _touch_job_heartbeat(job),
                redaction_values=redaction_values,
            )

        _set_stage(job, TemplateBuildJob.STAGE_POSTPROCESS)

        _write_json(paths["software_results"], {"items": software_results})
        job.status = TemplateBuildJob.STATUS_SUCCEEDED
        job.stage = TemplateBuildJob.STAGE_DONE
        job.finished_at = timezone.now()
        job.exit_code = 0
        job.error_summary = ""
        job.result_payload = {
            "software_results": software_results,
            "preflight": preflight_results,
            "generated_artifacts": generated_artifacts,
            "machine_readable_events": machine_readable_events,
            "guest_networking": payload.get("guest_networking") or "dhcp",
            "log_available": log_path.exists(),
        }
        _write_json(paths["result"], {"job": build_job_api_payload(job)})
        job.save(
            update_fields=[
                "status",
                "stage",
                "finished_at",
                "exit_code",
                "error_summary",
                "result_payload",
                "last_heartbeat_at",
                "updated_at",
            ]
        )
        archive_available = bool(_archive_job_bundle(job, paths, payload))
        if archive_available:
            job.result_payload["archive_available"] = True
            job.save(update_fields=["result_payload", "updated_at"])
            _write_json(paths["result"], {"job": build_job_api_payload(job)})
        _write_job_status_manifest(job)
        return job
    except Exception as exc:
        _write_json(paths["software_results"], {"items": software_results})
        job.status = TemplateBuildJob.STATUS_FAILED
        job.stage = TemplateBuildJob.STAGE_DONE
        job.finished_at = timezone.now()
        job.exit_code = 1 if job.exit_code is None else job.exit_code
        job.error_summary = str(exc)
        job.result_payload = {
            "software_results": software_results,
            "preflight": preflight_results,
            "generated_artifacts": generated_artifacts,
            "machine_readable_events": machine_readable_events,
            "guest_networking": payload.get("guest_networking") or "dhcp",
            "log_available": log_path.exists(),
        }
        job.save(
            update_fields=[
                "status",
                "stage",
                "finished_at",
                "exit_code",
                "error_summary",
                "result_payload",
                "last_heartbeat_at",
                "updated_at",
            ]
        )
        paths["error_summary"].write_text(job.error_summary, encoding="utf-8")
        _write_json(paths["result"], {"job": build_job_api_payload(job)})
        archive_available = bool(_archive_job_bundle(job, paths, payload))
        if archive_available:
            job.result_payload["archive_available"] = True
            job.save(update_fields=["result_payload", "updated_at"])
            _write_json(paths["result"], {"job": build_job_api_payload(job)})
        _write_job_status_manifest(job)
        return job


def _set_stage(job: TemplateBuildJob, stage: str):
    job.stage = stage
    job.save(update_fields=["stage", "updated_at"])
    _write_job_status_manifest(job)


def _resolve_template_file(build_profile: str, payload: dict) -> Path:
    template_dir = Path(__file__).resolve().parent / "packer" / "templates"
    if build_profile == BUILD_PROFILE_UBUNTU_AUTOINSTALL:
        path = template_dir / "ubuntu_autoinstall.pkr.hcl"
    elif build_profile == BUILD_PROFILE_DEBIAN_PRESEED:
        path = template_dir / "debian_preseed.pkr.hcl"
    elif build_profile == BUILD_PROFILE_WINDOWS_UNATTEND:
        windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
        if windows.get("firmware_profile") == WINDOWS_FIRMWARE_UEFI_TPM:
            path = template_dir / "windows_unattend_uefi.pkr.hcl"
        else:
            path = template_dir / "windows_unattend_bios.pkr.hcl"
    else:
        raise RuntimeError(f"Unsupported build profile: {build_profile}")

    if not path.exists():
        raise RuntimeError(f"Missing Packer template file: {path}")
    return path


def _run_preflight(build_profile: str, payload: dict, log_fp) -> list[dict]:
    results = []
    packer_bin = str(getattr(settings, "PACKER_BIN", "packer") or "packer")
    packer_resolved = shutil.which(packer_bin) if Path(packer_bin).name == packer_bin else str(Path(packer_bin))
    if not packer_resolved or (Path(packer_bin).name != packer_bin and not Path(packer_resolved).exists()):
        raise RuntimeError(f"Packer binary not found: {packer_bin}")
    results.append({"check": "packer_bin", "ok": True, "value": packer_resolved})
    log_fp.write(f"preflight: packer_bin={packer_resolved}\n")

    iso_tool = _detect_iso_tool()
    if not iso_tool:
        raise RuntimeError("No ISO authoring tool found. Configure PACKER_ISO_TOOL or install oscdimg/xorriso/mkisofs.")
    results.append({"check": "iso_tool", "ok": True, "value": iso_tool})
    log_fp.write(f"preflight: iso_tool={iso_tool}\n")

    plugin_source = str(getattr(settings, "PACKER_PROXMOX_PLUGIN_SOURCE", "") or "")
    plugin_version = str(getattr(settings, "PACKER_PROXMOX_PLUGIN_VERSION", "") or "")
    results.append({"check": "plugin", "ok": True, "value": f"{plugin_source} {plugin_version}".strip()})
    log_fp.write(f"preflight: plugin={plugin_source} {plugin_version}\n")

    if build_profile == BUILD_PROFILE_WINDOWS_UNATTEND:
        windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
        if not windows.get("virtio_iso_url"):
            raise RuntimeError("Windows build missing VirtIO ISO URL.")
    return results


def _detect_iso_tool() -> str:
    configured = str(getattr(settings, "PACKER_ISO_TOOL", "") or "").strip()
    if configured:
        resolved = shutil.which(configured) if Path(configured).name == configured else configured
        if resolved and (Path(resolved).exists() or Path(configured).name == configured):
            return str(resolved)

    for candidate in ["oscdimg", "xorriso", "mkisofs", "genisoimage"]:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return ""


def _write_profile_artifacts(build_profile: str, payload: dict, workspace: Path) -> tuple[list[dict], dict]:
    artifacts = []
    context = {}

    if build_profile == BUILD_PROFILE_UBUNTU_AUTOINSTALL:
        user_data = workspace / "user-data"
        meta_data = workspace / "meta-data"
        user_data.write_text(_render_ubuntu_user_data(payload), encoding="utf-8")
        meta_data.write_text(_render_meta_data(payload), encoding="utf-8")
        artifacts.extend(
            [
                _artifact_record("user_data", user_data, workspace.parent),
                _artifact_record("meta_data", meta_data, workspace.parent),
            ]
        )
        context.update(
            {
                "user_data_path": str(user_data.resolve()),
                "meta_data_path": str(meta_data.resolve()),
                "ssh_username": _FIXED_LINUX_USERNAME,
                "ssh_password": _FIXED_LINUX_PASSWORD,
                "ssh_timeout": str(payload.get("linux", {}).get("ssh_timeout") or "45m"),
            }
        )
        return artifacts, context

    if build_profile == BUILD_PROFILE_DEBIAN_PRESEED:
        preseed = workspace / "preseed.cfg"
        preseed.write_text(_render_debian_preseed(payload), encoding="utf-8")
        artifacts.append(_artifact_record("preseed", preseed, workspace.parent))
        context.update(
            {
                "preseed_path": str(preseed.resolve()),
                "ssh_username": _FIXED_LINUX_USERNAME,
                "ssh_password": _FIXED_LINUX_PASSWORD,
                "ssh_timeout": str(payload.get("linux", {}).get("ssh_timeout") or "45m"),
            }
        )
        return artifacts, context

    if build_profile == BUILD_PROFILE_WINDOWS_UNATTEND:
        unattend = workspace / "Autounattend.xml"
        unattend.write_text(_render_windows_unattend(payload), encoding="utf-8")
        artifacts.append(_artifact_record("autounattend", unattend, workspace.parent))
        windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
        context.update(
            {
                "autounattend_path": str(unattend.resolve()),
                "winrm_username": str(windows.get("admin_username") or ""),
                "winrm_password": str(windows.get("admin_password") or ""),
            }
        )
        return artifacts, context

    raise RuntimeError(f"Unsupported build profile: {build_profile}")


def _write_bootstrap_script(build_profile: str, target_os: str, payload: dict, workspace: Path) -> Path:
    software_items = payload.get("software_items") if isinstance(payload.get("software_items"), list) else []

    if build_profile == BUILD_PROFILE_WINDOWS_UNATTEND or target_os == TemplateDefinition.TARGET_OS_WINDOWS:
        path = workspace / "bootstrap.ps1"
        path.write_text(_render_windows_script(software_items), encoding="utf-8")
        return path

    path = workspace / "bootstrap.sh"
    path.write_text(_render_linux_script(software_items), encoding="utf-8")
    os.chmod(path, 0o755)
    return path


def _write_packer_vars_file(
    build_profile: str,
    target_os: str,
    payload: dict,
    workspace: Path,
    bootstrap_script: Path,
    profile_context: dict,
) -> Path:
    hardware = payload.get("hardware") if isinstance(payload.get("hardware"), dict) else {}
    network = payload.get("network") if isinstance(payload.get("network"), dict) else {}
    windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}

    vars_payload = {
        "proxmox_url": str(os.environ.get("PROXMOX_BASE_URL") or "").rstrip("/"),
        "proxmox_username": str(os.environ.get("PROXMOX_TOKEN_ID") or ""),
        "proxmox_token": str(os.environ.get("PROXMOX_TOKEN_SECRET") or ""),
        "proxmox_insecure_skip_tls_verify": str(os.environ.get("PROXMOX_TLS_VERIFY", "1")).strip().lower() not in {"1", "true", "yes", "on"},
        "proxmox_node": str(getattr(settings, "PROXMOX_NODE", "") or "pve"),
        "storage_pool": str(getattr(settings, "PROXMOX_STORAGE_POOL", "local-lvm")),
        "iso_storage_pool": str(getattr(settings, "PROXMOX_ISO_STORAGE_POOL", "local")),
        "template_name": str(payload.get("template_name") or "").strip(),
        "template_vmid": int(payload.get("template_vmid") or 0),
        "iso_url": str(payload.get("iso_url") or "").strip(),
        "iso_checksum": str(payload.get("iso_checksum") or "none"),
        "cpu": int(hardware.get("cpu") or 2),
        "ram_mb": int(hardware.get("ram_gb") or 4) * 1024,
        "disk_gb": int(hardware.get("disk_gb") or 32),
        "bridge": str(network.get("bridge") or "vmbr0"),
        "vlan": int(network.get("vlan") or 0),
        "bootstrap_script": str(bootstrap_script.resolve()),
    }
    vars_payload.update(profile_context)

    if build_profile == BUILD_PROFILE_WINDOWS_UNATTEND:
        vars_payload.update(
            {
                "windows_virtio_iso_url": str(windows.get("virtio_iso_url") or ""),
                "windows_image_selector_type": str(windows.get("image_selector_type") or "image_name"),
                "windows_image_selector_value": str(windows.get("image_selector_value") or ""),
                "windows_firmware_profile": str(windows.get("firmware_profile") or ""),
                "winrm_port": int(windows.get("winrm_port") or 5985),
                "winrm_use_ssl": bool(windows.get("winrm_use_ssl", False)),
                "winrm_timeout": str(windows.get("winrm_timeout") or "2h"),
            }
        )

    vars_path = workspace / "template.auto.pkrvars.json"
    vars_path.write_text(json.dumps(vars_payload, indent=2), encoding="utf-8")
    return vars_path


def _build_redaction_values(payload: dict) -> list[str]:
    values = [
        str(os.environ.get("PROXMOX_TOKEN_SECRET") or "").strip(),
    ]
    windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
    values.extend(
        [
            str(windows.get("admin_password") or "").strip(),
            str(windows.get("winrm_password") or "").strip(),
        ]
    )
    return [value for value in values if value]


def _redact_text(text: str, redaction_values: list[str]) -> str:
    redacted = text
    for value in redaction_values:
        redacted = redacted.replace(value, "[REDACTED]")
    return redacted


def _parse_machine_readable_event(line: str) -> dict | None:
    parts = [part.strip() for part in str(line or "").split(",")]
    if len(parts) < 3:
        return None
    if not parts[0].isdigit():
        return None
    return {
        "timestamp": parts[0],
        "target": parts[1] or None,
        "type": parts[2],
        "data": parts[3:],
    }


def _archive_job_bundle(job: TemplateBuildJob, paths: dict[str, Path], payload: dict) -> Path | None:
    archive_root = Path(settings.PACKER_NAS_ARCHIVE_DIR)
    nas_root = Path(settings.PACKER_NAS_ROOT)
    if not nas_root.exists():
        return None

    archive_dir = archive_root / f"job-{job.uuid}"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for name in ["request", "status", "result", "software_results", "preflight"]:
        source = paths[name]
        if source.exists():
            shutil.copy2(source, archive_dir / source.name)
    if paths["packer_log"].exists():
        shutil.copy2(paths["packer_log"], archive_dir / paths["packer_log"].name)
    if paths["error_summary"].exists():
        shutil.copy2(paths["error_summary"], archive_dir / paths["error_summary"].name)
    return archive_dir


def _run_dev_bypass_job(
    job: TemplateBuildJob,
    paths: dict[str, Path],
    payload: dict,
    software_results: list[dict],
    machine_readable_events: list[dict],
) -> TemplateBuildJob:
    _set_stage(job, TemplateBuildJob.STAGE_PREFLIGHT)
    _touch_job_heartbeat(job)

    preflight_results = [
        {"check": "packer_bin", "ok": True, "skipped": True, "reason": "dev_bypass"},
        {"check": "iso_tool", "ok": True, "skipped": True, "reason": "dev_bypass"},
    ]
    _write_json(paths["preflight"], {"checks": preflight_results})
    _write_json(paths["software_results"], {"items": []})
    paths["packer_log"].write_text(
        "dev mode execution\n"
        "skipped real packer init/validate/build because TEMPLATE_BUILD_DEV_BYPASS=1\n",
        encoding="utf-8",
    )

    summary = "Dev mode execution: queue consumed without real Packer build."
    job.status = TemplateBuildJob.STATUS_SUCCEEDED
    job.stage = TemplateBuildJob.STAGE_DONE
    job.finished_at = timezone.now()
    job.last_heartbeat_at = timezone.now()
    job.exit_code = 0
    job.error_summary = ""
    job.result_payload = {
        "software_results": software_results,
        "preflight": preflight_results,
        "generated_artifacts": [],
        "machine_readable_events": machine_readable_events,
        "guest_networking": payload.get("guest_networking") or "dhcp",
        "log_available": True,
        "dev_bypass": True,
        "execution_mode": "dev_bypass",
        "summary": summary,
        "archive_available": False,
    }
    job.save(
        update_fields=[
            "status",
            "stage",
            "finished_at",
            "last_heartbeat_at",
            "exit_code",
            "error_summary",
            "result_payload",
            "updated_at",
        ]
    )
    _write_json(paths["result"], {"job": build_job_api_payload(job)})
    _write_job_status_manifest(job)
    return job


def _parse_result_marker(line: str) -> dict | None:
    m = _RESULT_MARKER_RE.search(line)
    if not m:
        return None
    item_id, status, code, message = m.groups()
    try:
        exit_code = int(code)
    except Exception:
        exit_code = None
    return {
        "item_id": item_id,
        "status": status,
        "exit_code": exit_code,
        "message": message,
    }


def _parse_stage_marker(line: str) -> str:
    m = _STAGE_MARKER_RE.search(line)
    if not m:
        return ""
    return m.group(1).strip().lower()


def _run_command(
    cmd: list[str],
    cwd: Path,
    timeout_sec: int,
    log_fp,
    on_output: Callable[[str], None],
    heartbeat_cb: Callable[[], None] | None = None,
    redaction_values: list[str] | None = None,
):
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {cmd[0]}") from exc

    assert process.stdout is not None
    output_queue: queue.Queue[str | None] = queue.Queue()

    def _reader():
        try:
            assert process.stdout is not None
            for line in process.stdout:
                output_queue.put(line)
        finally:
            output_queue.put(None)

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    last_heartbeat = time.monotonic()
    redaction_values = redaction_values or []

    while True:
        if time.monotonic() - started > timeout_sec:
            process.kill()
            raise RuntimeError(f"Command timed out after {timeout_sec}s: {' '.join(cmd)}")

        try:
            line = output_queue.get(timeout=1)
        except queue.Empty:
            line = None

        if heartbeat_cb and time.monotonic() - last_heartbeat >= max(1, settings.TEMPLATE_BUILD_HEARTBEAT_SECONDS):
            heartbeat_cb()
            last_heartbeat = time.monotonic()

        if line is None:
            if process.poll() is not None and not thread.is_alive():
                break
            continue

        redacted_line = _redact_text(line, redaction_values)
        log_fp.write(redacted_line)
        log_fp.flush()
        on_output(redacted_line.rstrip("\n"))

    code = process.wait()
    if heartbeat_cb:
        heartbeat_cb()
    if code != 0:
        raise RuntimeError(f"Command failed ({code}): {' '.join(cmd)}")


def _render_linux_script(software_items: list[dict]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -u",
        "set +e",
        'MARKER="CAPSTONE_ITEM_RESULT"',
        "if command -v sudo >/dev/null 2>&1; then SUDO=sudo; else SUDO=; fi",
        "mkdir -p /tmp/capstone-software",
        "emit_result() {",
        '  local item_id="$1" status="$2" code="$3" message="$4"',
        '  message="${message//|/ }"',
        '  echo "${MARKER}|${item_id}|${status}|${code}|${message}"',
        "}",
        "run_cmd() {",
        '  local item_id="$1" message="$2"',
        "  shift 2",
        '  "$@"',
        "  local rc=$?",
        "  if [ $rc -eq 0 ]; then",
        '    emit_result "$item_id" "installed" "$rc" "$message"',
        "  else",
        '    emit_result "$item_id" "failed" "$rc" "$message"',
        "  fi",
        "}",
        "if command -v apt-get >/dev/null 2>&1; then",
        '  bash -lc "$SUDO apt-get update -y && $SUDO apt-get install -y qemu-guest-agent cloud-init curl unzip tar" >/dev/null 2>&1',
        "elif command -v dnf >/dev/null 2>&1; then",
        '  bash -lc "$SUDO dnf install -y qemu-guest-agent cloud-init curl unzip tar" >/dev/null 2>&1',
        "elif command -v yum >/dev/null 2>&1; then",
        '  bash -lc "$SUDO yum install -y qemu-guest-agent cloud-init curl unzip tar" >/dev/null 2>&1',
        "fi",
        'bash -lc "$SUDO systemctl enable qemu-guest-agent >/dev/null 2>&1 || true"',
    ]

    for idx, item in enumerate(software_items, start=1):
        item_id = str(item.get("id") or f"item-{idx}")
        kind = str(item.get("kind") or "")
        label = str(item.get("label") or item.get("name") or item.get("url") or item_id)
        artifact = str(item.get("artifact_type") or "unknown")
        silent_args = str(item.get("silent_args") or "")

        if kind == "package":
            pkg = str(item.get("name") or label)
            pkg_q = shlex.quote(pkg)
            lines.extend(
                [
                    f"# {label}",
                    "if command -v apt-get >/dev/null 2>&1; then",
                    f"  run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc \"$SUDO apt-get update -y && $SUDO apt-get install -y {pkg_q}\"",
                    "elif command -v dnf >/dev/null 2>&1; then",
                    f"  run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc \"$SUDO dnf install -y {pkg_q}\"",
                    "elif command -v yum >/dev/null 2>&1; then",
                    f"  run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc \"$SUDO yum install -y {pkg_q}\"",
                    "elif command -v apk >/dev/null 2>&1; then",
                    f"  run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc \"$SUDO apk add {pkg_q}\"",
                    "else",
                    f"  emit_result {shlex.quote(item_id)} failed 127 {shlex.quote('No supported package manager found')}",
                    "fi",
                ]
            )
            continue

        url = str(item.get("url") or "").strip()
        if not url:
            lines.append(f"emit_result {shlex.quote(item_id)} failed 1 {shlex.quote('Missing URL')}")
            continue

        filename = Path(url).name or f"download-{idx}.bin"
        dest = f"/tmp/capstone-software/{filename}"
        lines.append(f"curl -fsSL {shlex.quote(url)} -o {shlex.quote(dest)} || wget -qO {shlex.quote(dest)} {shlex.quote(url)}")

        if artifact == "deb":
            cmd = f"$SUDO dpkg -i {shlex.quote(dest)} || $SUDO apt-get install -f -y"
            lines.append(f"run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc {shlex.quote(cmd)}")
        elif artifact == "rpm":
            cmd = f"$SUDO rpm -Uvh --nosignature {shlex.quote(dest)}"
            lines.append(f"run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc {shlex.quote(cmd)}")
        elif artifact == "apk":
            cmd = f"$SUDO apk add --allow-untrusted {shlex.quote(dest)}"
            lines.append(f"run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc {shlex.quote(cmd)}")
        elif artifact in {"zip", "tar"}:
            extract_dir = f"/opt/capstone/{item_id}"
            if artifact == "zip":
                cmd = f"mkdir -p {shlex.quote(extract_dir)} && unzip -o {shlex.quote(dest)} -d {shlex.quote(extract_dir)}"
            else:
                cmd = f"mkdir -p {shlex.quote(extract_dir)} && tar -xf {shlex.quote(dest)} -C {shlex.quote(extract_dir)}"
            lines.append(f"run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc {shlex.quote(cmd)}")
        else:
            cmd = f"chmod +x {shlex.quote(dest)} && {shlex.quote(dest)} {silent_args}".strip()
            lines.append(f"run_cmd {shlex.quote(item_id)} {shlex.quote(label)} bash -lc {shlex.quote(cmd)}")

    lines.append("exit 0")
    return "\n".join(lines) + "\n"


def _render_windows_script(software_items: list[dict]) -> str:
    lines = [
        '$ErrorActionPreference = "Continue"',
        '$marker = "CAPSTONE_ITEM_RESULT"',
        '$tempDir = "C:\\Windows\\Temp\\capstone-software"',
        'New-Item -Path $tempDir -ItemType Directory -Force | Out-Null',
        "",
        "function Emit-Result {",
        "  param([string]$ItemId, [string]$Status, [int]$Code, [string]$Message)",
        '  $safe = $Message -replace "\\|", " "',
        '  Write-Output "$marker|$ItemId|$Status|$Code|$safe"',
        "}",
        "",
        "function Find-VirtioGuestAgentInstaller {",
        '  $candidatePaths = @("guest-agent\\qemu-ga-x86_64.msi", "guest-agent\\qemu-ga.msi")',
        "  foreach ($drive in Get-PSDrive -PSProvider FileSystem) {",
        "    foreach ($relativePath in $candidatePaths) {",
        "      $candidate = Join-Path $drive.Root $relativePath",
        "      if (Test-Path $candidate) {",
        "        return $candidate",
        "      }",
        "    }",
        "  }",
        "  return $null",
        "}",
        "",
        '$guestAgentInstaller = Find-VirtioGuestAgentInstaller',
        "if ($guestAgentInstaller) {",
        '  $guestAgentArgs = "/i `"${guestAgentInstaller}`" /qn /norestart"',
        "  $guestAgentCode = 0",
        "  try {",
        "    Start-Process -FilePath msiexec.exe -ArgumentList $guestAgentArgs -Wait -PassThru | Out-Null",
        "    if ($LASTEXITCODE -ne $null) { $guestAgentCode = [int]$LASTEXITCODE }",
        "  } catch {",
        "    $guestAgentCode = 1",
        "  }",
        "  if ($guestAgentCode -eq 0) {",
        "    Emit-Result 'qemu-guest-agent' 'installed' $guestAgentCode 'QEMU guest agent installed'",
        "  } else {",
        "    Emit-Result 'qemu-guest-agent' 'failed' $guestAgentCode 'QEMU guest agent install failed'",
        "  }",
        "} else {",
        "  Emit-Result 'qemu-guest-agent' 'failed' 1 'VirtIO guest agent installer not found'",
        "}",
        "",
    ]

    for idx, item in enumerate(software_items, start=1):
        item_id = str(item.get("id") or f"item-{idx}")
        label = str(item.get("label") or item.get("name") or item.get("url") or item_id)
        kind = str(item.get("kind") or "")
        artifact = str(item.get("artifact_type") or "unknown")
        silent_args = str(item.get("silent_args") or "")

        lines.append(f"# {label}")
        if kind == "package":
            lines.append(f"Emit-Result '{item_id}' 'failed' 1 'Package manager installs are not supported on Windows bootstrap script.'")
            continue

        url = str(item.get("url") or "").strip()
        if not url:
            lines.append(f"Emit-Result '{item_id}' 'failed' 1 'Missing URL'")
            continue

        filename = Path(url).name or f"download-{idx}.bin"
        filepath = f"$tempDir\\{filename}"

        lines.extend(
            [
                "try {",
                f"  Invoke-WebRequest -Uri '{url}' -OutFile \"{filepath}\" -UseBasicParsing",
                "} catch {",
                f"  Emit-Result '{item_id}' 'failed' 1 ('Download failed: ' + $_.Exception.Message)",
                "  continue",
                "}",
            ]
        )

        if artifact == "exe":
            exec_cmd = f"Start-Process -FilePath \"{filepath}\" -ArgumentList '{silent_args}' -Wait -PassThru"
        elif artifact == "msi":
            exec_cmd = f"Start-Process -FilePath msiexec.exe -ArgumentList '/i `\"{filepath}`\" {silent_args}' -Wait -PassThru"
        elif artifact == "msix":
            exec_cmd = f"Add-AppxPackage -Path \"{filepath}\""
        elif artifact == "zip":
            exec_cmd = f"Expand-Archive -Path \"{filepath}\" -DestinationPath \"$tempDir\\{item_id}\" -Force"
        elif artifact == "ps1":
            exec_cmd = f"PowerShell -ExecutionPolicy Bypass -File \"{filepath}\" {silent_args}".strip()
        elif artifact in {"bat", "cmd"}:
            exec_cmd = f"cmd /c \"{filepath} {silent_args}\"".strip()
        else:
            exec_cmd = f"PowerShell -ExecutionPolicy Bypass -File \"{filepath}\" {silent_args}".strip()

        lines.extend(
            [
                "$code = 0",
                "try {",
                f"  {exec_cmd} | Out-Null",
                "  if ($LASTEXITCODE -ne $null) { $code = [int]$LASTEXITCODE }",
                "} catch {",
                "  $code = 1",
                "}",
                "if ($code -eq 0) {",
                f"  Emit-Result '{item_id}' 'installed' $code '{label}'",
                "} else {",
                f"  Emit-Result '{item_id}' 'failed' $code '{label}'",
                "}",
            ]
        )

    lines.append('Write-Output "CAPSTONE_STAGE|sealing"')
    lines.append('Start-Process -FilePath "$env:SystemRoot\\System32\\Sysprep\\Sysprep.exe" -ArgumentList "/oobe /generalize /shutdown /quiet" -WindowStyle Hidden')
    lines.append("Start-Sleep -Seconds 10")
    lines.append("exit 0")
    return "\n".join(lines) + "\n"


def _render_meta_data(payload: dict) -> str:
    template_name = str(payload.get("template_name") or "capstone-template").strip()
    return f"instance-id: {template_name}\nlocal-hostname: {template_name}\n"


def _render_ubuntu_user_data(payload: dict) -> str:
    template_name = str(payload.get("template_name") or "capstone-template").strip()
    return (
        "#cloud-config\n"
        "autoinstall:\n"
        "  version: 1\n"
        "  identity:\n"
        f"    hostname: {template_name}\n"
        f"    username: {_FIXED_LINUX_USERNAME}\n"
        f"    password: {_FIXED_LINUX_PASSWORD_HASH}\n"
        "  ssh:\n"
        "    install-server: true\n"
        "    allow-pw: true\n"
        "  packages:\n"
        "    - qemu-guest-agent\n"
        "    - cloud-init\n"
        "  late-commands:\n"
        "    - curtin in-target --target=/target systemctl enable qemu-guest-agent\n"
    )


def _render_debian_preseed(payload: dict) -> str:
    template_name = str(payload.get("template_name") or "capstone-template").strip()
    return (
        "d-i debian-installer/locale string en_US.UTF-8\n"
        "d-i keyboard-configuration/xkb-keymap select us\n"
        "d-i netcfg/choose_interface select auto\n"
        f"d-i netcfg/get_hostname string {template_name}\n"
        "d-i netcfg/get_domain string local\n"
        "d-i time/zone string UTC\n"
        "d-i passwd/root-login boolean false\n"
        f"d-i passwd/user-fullname string {_FIXED_LINUX_USERNAME}\n"
        f"d-i passwd/username string {_FIXED_LINUX_USERNAME}\n"
        f"d-i passwd/user-password password {_FIXED_LINUX_PASSWORD}\n"
        f"d-i passwd/user-password-again password {_FIXED_LINUX_PASSWORD}\n"
        "d-i user-setup/allow-password-weak boolean true\n"
        "tasksel tasksel/first multiselect standard, ssh-server\n"
        "d-i pkgsel/include string qemu-guest-agent cloud-init sudo curl unzip\n"
        "d-i grub-installer/only_debian boolean true\n"
        "d-i finish-install/reboot_in_progress note\n"
    )


def _render_windows_unattend(payload: dict) -> str:
    windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
    admin_username = xml_escape(str(windows.get("admin_username") or "capstoneadmin"))
    admin_password = xml_escape(str(windows.get("admin_password") or ""))
    selector_type = str(windows.get("image_selector_type") or "image_name")
    selector_value = xml_escape(str(windows.get("image_selector_value") or ""))
    firmware_profile = str(windows.get("firmware_profile") or WINDOWS_FIRMWARE_BIOS_LEGACY)
    install_key = "/IMAGE/INDEX" if selector_type == "image_index" else "/IMAGE/NAME"
    disk_configuration = _render_windows_disk_configuration_xml(firmware_profile)
    install_partition_id = "3" if firmware_profile == WINDOWS_FIRMWARE_UEFI_TPM else "2"
    first_logon_script = xml_escape(
        "powershell -ExecutionPolicy Bypass -Command "
        "\"Enable-PSRemoting -SkipNetworkProfileCheck -Force; "
        "winrm quickconfig -q; "
        "Set-Item -Path WSMan:\\localhost\\Service\\AllowUnencrypted -Value $true; "
        "Set-Item -Path WSMan:\\localhost\\Service\\Auth\\Basic -Value $true; "
        "sc.exe config winrm start= auto; "
        "Restart-Service WinRM; "
        "Set-NetFirewallRule -DisplayGroup 'Windows Remote Management' -Enabled True\""
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
  <settings pass="windowsPE">
    <component name="Microsoft-Windows-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      {disk_configuration}
      <ImageInstall>
        <OSImage>
          <InstallFrom>
            <MetaData wcm:action="add" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
              <Key>{install_key}</Key>
              <Value>{selector_value}</Value>
            </MetaData>
          </InstallFrom>
          <WillShowUI>OnError</WillShowUI>
          <InstallTo>
            <DiskID>0</DiskID>
            <PartitionID>{install_partition_id}</PartitionID>
          </InstallTo>
        </OSImage>
      </ImageInstall>
      <UserData>
        <AcceptEula>true</AcceptEula>
      </UserData>
    </component>
  </settings>
  <settings pass="oobeSystem">
    <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
      <AutoLogon>
        <Enabled>true</Enabled>
        <Username>{admin_username}</Username>
        <LogonCount>2</LogonCount>
        <Password>
          <Value>{admin_password}</Value>
          <PlainText>true</PlainText>
        </Password>
      </AutoLogon>
      <UserAccounts>
        <LocalAccounts>
          <LocalAccount wcm:action="add" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
            <Name>{admin_username}</Name>
            <DisplayName>{admin_username}</DisplayName>
            <Group>Administrators</Group>
            <Password>
              <Value>{admin_password}</Value>
              <PlainText>true</PlainText>
            </Password>
          </LocalAccount>
        </LocalAccounts>
        <AdministratorPassword>
          <Value>{admin_password}</Value>
          <PlainText>true</PlainText>
        </AdministratorPassword>
      </UserAccounts>
      <FirstLogonCommands>
        <SynchronousCommand wcm:action="add" xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
          <Order>1</Order>
          <Description>Enable WinRM</Description>
          <CommandLine>{first_logon_script}</CommandLine>
        </SynchronousCommand>
      </FirstLogonCommands>
      <OOBE>
        <HideEULAPage>true</HideEULAPage>
        <HideLocalAccountScreen>true</HideLocalAccountScreen>
        <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
        <ProtectYourPC>3</ProtectYourPC>
      </OOBE>
    </component>
  </settings>
</unattend>
"""


def _render_windows_disk_configuration_xml(firmware_profile: str) -> str:
    if firmware_profile == WINDOWS_FIRMWARE_UEFI_TPM:
        return (
            "<DiskConfiguration>\n"
            "        <Disk wcm:action=\"add\" xmlns:wcm=\"http://schemas.microsoft.com/WMIConfig/2002/State\">\n"
            "          <DiskID>0</DiskID>\n"
            "          <WillWipeDisk>true</WillWipeDisk>\n"
            "          <CreatePartitions>\n"
            "            <CreatePartition wcm:action=\"add\">\n"
            "              <Order>1</Order>\n"
            "              <Type>EFI</Type>\n"
            "              <Size>100</Size>\n"
            "            </CreatePartition>\n"
            "            <CreatePartition wcm:action=\"add\">\n"
            "              <Order>2</Order>\n"
            "              <Type>MSR</Type>\n"
            "              <Size>16</Size>\n"
            "            </CreatePartition>\n"
            "            <CreatePartition wcm:action=\"add\">\n"
            "              <Order>3</Order>\n"
            "              <Type>Primary</Type>\n"
            "              <Extend>true</Extend>\n"
            "            </CreatePartition>\n"
            "          </CreatePartitions>\n"
            "          <ModifyPartitions>\n"
            "            <ModifyPartition wcm:action=\"add\">\n"
            "              <Order>1</Order>\n"
            "              <PartitionID>1</PartitionID>\n"
            "              <Format>FAT32</Format>\n"
            "              <Label>System</Label>\n"
            "            </ModifyPartition>\n"
            "            <ModifyPartition wcm:action=\"add\">\n"
            "              <Order>2</Order>\n"
            "              <PartitionID>3</PartitionID>\n"
            "              <Format>NTFS</Format>\n"
            "              <Label>Windows</Label>\n"
            "              <Letter>C</Letter>\n"
            "            </ModifyPartition>\n"
            "          </ModifyPartitions>\n"
            "        </Disk>\n"
            "      </DiskConfiguration>"
        )

    return (
        "<DiskConfiguration>\n"
        "        <Disk wcm:action=\"add\" xmlns:wcm=\"http://schemas.microsoft.com/WMIConfig/2002/State\">\n"
        "          <DiskID>0</DiskID>\n"
        "          <WillWipeDisk>true</WillWipeDisk>\n"
        "          <CreatePartitions>\n"
        "            <CreatePartition wcm:action=\"add\">\n"
        "              <Order>1</Order>\n"
        "              <Type>Primary</Type>\n"
        "              <Size>500</Size>\n"
        "            </CreatePartition>\n"
        "            <CreatePartition wcm:action=\"add\">\n"
        "              <Order>2</Order>\n"
        "              <Type>Primary</Type>\n"
        "              <Extend>true</Extend>\n"
        "            </CreatePartition>\n"
        "          </CreatePartitions>\n"
        "          <ModifyPartitions>\n"
        "            <ModifyPartition wcm:action=\"add\">\n"
        "              <Order>1</Order>\n"
        "              <PartitionID>1</PartitionID>\n"
        "              <Active>true</Active>\n"
        "              <Format>NTFS</Format>\n"
        "              <Label>System</Label>\n"
        "            </ModifyPartition>\n"
        "            <ModifyPartition wcm:action=\"add\">\n"
        "              <Order>2</Order>\n"
        "              <PartitionID>2</PartitionID>\n"
        "              <Format>NTFS</Format>\n"
        "              <Label>Windows</Label>\n"
        "              <Letter>C</Letter>\n"
        "            </ModifyPartition>\n"
        "          </ModifyPartitions>\n"
        "        </Disk>\n"
        "      </DiskConfiguration>"
    )
