import os
import re

from django.conf import settings
from django.utils import timezone

from .client import ProxmoxClient
from core.models import VirtualMachine

_client = None
_PRIMARY_DISK_RE = re.compile(r"^([a-z]+)(\d+)$", re.IGNORECASE)
_SIZE_RE = re.compile(r"size=(\d+(?:\.\d+)?)([KMGTP])", re.IGNORECASE)


def _client_instance():
    global _client
    if _client is None:
        _client = ProxmoxClient()
    return _client


def _looks_like_task_id(value) -> bool:
    return isinstance(value, str) and value.startswith("UPID:")


def _wait_for_task_if_needed(client: ProxmoxClient, node: str, value, timeout_sec: int = 120):
    if _looks_like_task_id(value):
        client.wait_for_task(node=node, upid=value, timeout_sec=timeout_sec)


def _primary_disk_key(vm_config: dict) -> str | None:
    preferred = ["scsi0", "virtio0", "sata0", "ide0"]
    for key in preferred:
        if vm_config.get(key):
            return key

    disk_keys = []
    for key, value in (vm_config or {}).items():
        if not value or _PRIMARY_DISK_RE.fullmatch(str(key or "")) is None:
            continue
        disk_keys.append(str(key))

    if not disk_keys:
        return None
    return sorted(disk_keys)[0]


def _disk_size_gb(vm_config: dict, disk_key: str | None) -> int | None:
    if not disk_key:
        return None
    entry = str((vm_config or {}).get(disk_key) or "")
    match = _SIZE_RE.search(entry)
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {
        "K": 1 / (1024 * 1024),
        "M": 1 / 1024,
        "G": 1,
        "T": 1024,
        "P": 1024 * 1024,
    }
    gb_value = value * multipliers.get(unit, 1)
    return max(1, int(gb_value if gb_value.is_integer() else gb_value + 0.999))


def _network_config_payload(network: dict) -> dict:
    bridge = str(network.get("bridge") or "").strip()
    parts = ["virtio", f"bridge={bridge}"]
    vlan = network.get("vlan")
    if vlan not in {None, "", 0}:
        parts.append(f"tag={int(vlan)}")

    payload = {
        "net0": ",".join(parts),
    }

    ipv4_mode = str(network.get("ipv4_mode") or "dhcp").strip().lower()
    if ipv4_mode == "static":
        payload["ipconfig0"] = (
            f"ip={network.get('static_ip')},gw={network.get('static_gateway')}"
        )
        dns_values = network.get("static_dns") if isinstance(network.get("static_dns"), list) else []
        if dns_values:
            payload["nameserver"] = " ".join(str(item).strip() for item in dns_values if str(item).strip())
    else:
        payload["ipconfig0"] = "ip=dhcp"

    return payload


def provision_vm_from_template(
    *,
    owner,
    template_definition,
    name: str,
    hardware: dict,
    network: dict,
):
    client = _client_instance()
    node = str(getattr(settings, "PROXMOX_NODE", "") or "").strip()
    if not node:
        raise RuntimeError("PROXMOX_NODE is not configured.")

    source_vmid = int(str(template_definition.template_vmid or "").strip())
    proxmox_vmid = client.allocate_next_vmid()
    vm_name = str(name or "").strip()
    vm_record = VirtualMachine.objects.create(
        owner=owner,
        template_definition=template_definition,
        proxmox_vmid=proxmox_vmid,
        name=vm_name,
        node=node,
        hardware=hardware,
        network=network,
        status=VirtualMachine.STATUS_PROVISIONING,
    )

    try:
        clone_upid = client.clone_from_template(
            node=node,
            template_vmid=source_vmid,
            new_vmid=proxmox_vmid,
            name=vm_name,
        )
        vm_record.task_upid = str(clone_upid or "")
        vm_record.save(update_fields=["task_upid", "updated_at"])
        _wait_for_task_if_needed(client, node, clone_upid, timeout_sec=600)

        config_payload = {
            "cores": int(hardware.get("cpu") or 1),
            "memory": int(hardware.get("ram_gb") or 1) * 1024,
        }
        config_payload.update(_network_config_payload(network))
        config_result = client.update_vm_config(node=node, vmid=proxmox_vmid, config=config_payload)
        if _looks_like_task_id(config_result):
            vm_record.task_upid = config_result
            vm_record.save(update_fields=["task_upid", "updated_at"])
            _wait_for_task_if_needed(client, node, config_result, timeout_sec=180)

        vm_config = client.get_vm_config(node=node, vmid=proxmox_vmid)
        disk_key = _primary_disk_key(vm_config)
        current_disk_gb = _disk_size_gb(vm_config, disk_key)
        requested_disk_gb = int(hardware.get("disk_gb") or 0)
        if disk_key and requested_disk_gb and (current_disk_gb is None or requested_disk_gb > current_disk_gb):
            resize_result = client.resize_disk(node=node, vmid=proxmox_vmid, disk=disk_key, size_gb=requested_disk_gb)
            if _looks_like_task_id(resize_result):
                vm_record.task_upid = resize_result
                vm_record.save(update_fields=["task_upid", "updated_at"])
                _wait_for_task_if_needed(client, node, resize_result, timeout_sec=300)

        start_upid = client.start_vm(node=node, vmid=proxmox_vmid)
        vm_record.task_upid = str(start_upid or "")
        vm_record.save(update_fields=["task_upid", "updated_at"])
        _wait_for_task_if_needed(client, node, start_upid, timeout_sec=180)

    except Exception as exc:
        vm_record.status = VirtualMachine.STATUS_FAILED
        vm_record.last_error = str(exc)
        vm_record.save(update_fields=["status", "last_error", "updated_at"])
        raise

    now = timezone.now()
    vm_record.status = VirtualMachine.STATUS_RUNNING
    vm_record.last_error = ""
    vm_record.provisioned_at = now
    vm_record.started_at = now
    vm_record.save(
        update_fields=[
            "status",
            "last_error",
            "provisioned_at",
            "started_at",
            "updated_at",
        ]
    )
    return vm_record


def provision_default_vm(node: str, vmid: int):
    client = _client_instance()

    template_vmid = int(os.environ.get("PROXMOX_TEMPLATE_VMID", "1002"))
    vm_name = f"capstone-{vmid}"

    upid = client.clone_from_template(
        node=node,
        template_vmid=template_vmid,
        new_vmid=vmid,
        name=vm_name,
    )

    client.wait_for_task(node=node, upid=upid)

    return client.start_vm(node=node, vmid=vmid)
