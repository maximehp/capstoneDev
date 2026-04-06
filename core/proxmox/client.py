import os
import time

import requests
import urllib3


def normalize_proxmox_api_base(raw_url: str) -> str:
    base_url = str(raw_url or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("Missing PROXMOX_BASE_URL")
    if base_url.endswith("/api2/json"):
        return base_url
    if base_url.endswith("/api2"):
        return base_url + "/json"
    return base_url + "/api2/json"


class ProxmoxClient:
    def __init__(self):
        self.base_url = normalize_proxmox_api_base(os.environ["PROXMOX_BASE_URL"])
        self.api_id = os.environ["PROXMOX_TOKEN_ID"]
        self.api_secret = os.environ["PROXMOX_TOKEN_SECRET"]
        self.tls_verify = os.environ.get("PROXMOX_TLS_VERIFY", "1") == "1"

        if not self.tls_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _headers(self):
        return {
            "Accept": "application/json",
            "Authorization": f"PVEAPIToken={self.api_id}={self.api_secret}",
        }

    def _api_url(self, path: str) -> str:
        suffix = path if str(path).startswith("/") else f"/{path}"
        return f"{self.base_url}{suffix}"

    def _request_json(self, method: str, path: str, timeout: int = 20, **kwargs):
        resp = requests.request(
            method,
            self._api_url(path),
            headers=self._headers(),
            verify=self.tls_verify,
            timeout=timeout,
            **kwargs,
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def allocate_next_vmid(self) -> int:
        value = self._request_json("GET", "/cluster/nextid", timeout=20)
        return int(value)

    def clone_from_template(self, node: str, template_vmid: int, new_vmid: int, name: str):
        return self._request_json(
            "POST",
            f"/nodes/{node}/qemu/{template_vmid}/clone",
            timeout=300,
            data={
                "newid": str(new_vmid),
                "name": name,
                "full": "0",
            },
        )

    def get_vm_config(self, node: str, vmid: int):
        return self._request_json("GET", f"/nodes/{node}/qemu/{vmid}/config", timeout=20)

    def update_vm_config(self, node: str, vmid: int, config: dict):
        return self._request_json(
            "POST",
            f"/nodes/{node}/qemu/{vmid}/config",
            timeout=60,
            data=config,
        )

    def resize_disk(self, node: str, vmid: int, disk: str, size_gb: int):
        return self._request_json(
            "PUT",
            f"/nodes/{node}/qemu/{vmid}/resize",
            timeout=120,
            data={
                "disk": disk,
                "size": f"{int(size_gb)}G",
            },
        )

    def start_vm(self, node: str, vmid: int):
        return self._request_json("POST", f"/nodes/{node}/qemu/{vmid}/status/start", timeout=20)

    def wait_for_task(self, node: str, upid: str, timeout_sec: int = 120):
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            data = self._request_json("GET", f"/nodes/{node}/tasks/{upid}/status", timeout=20)
            if data["status"] == "stopped":
                if data.get("exitstatus") != "OK":
                    raise RuntimeError(f"Task failed: {data.get('exitstatus')}")
                return
            time.sleep(2)
        raise TimeoutError("Timed out waiting for Proxmox task")
