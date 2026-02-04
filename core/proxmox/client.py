import os
import time
import requests
import urllib3


class ProxmoxClient:
    def __init__(self):
        self.base_url = os.environ["PROXMOX_BASE_URL"].rstrip("/")
        self.api_id = os.environ["PROXMOX_TOKEN_ID"]
        self.api_secret = os.environ["ProxMOX_TOKEN_SECRET"]
        self.tls_verify = os.environ.get("PROXMOX_TLS_VERIFY", "1") == "1"

        if not self.tls_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _headers(self):
        return {
            "Authorization": f"PVEAPIToken={self.api_id}={self.api_secret}"
        }

    def clone_from_template(self, node: str, template_vmid: int, new_vmid: int, name: str):
        url = f"{self.base_url}/api2/json/nodes/{node}/qemu/{template_vmid}/clone"
        resp = requests.post(
            url,
            headers=self._headers(),
            verify=self.tls_verify,
            timeout=60,
            data={
                "newid": str(new_vmid),
                "name": name,
                "full": "1",
            },
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def start_vm(self, node: str, vmid: int):
        url = f"{self.base_url}/api2/json/nodes/{node}/qemu/{vmid}/status/start"
        resp = requests.post(
            url,
            headers=self._headers(),
            verify=self.tls_verify,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def wait_for_task(self, node: str, upid: str, timeout_sec: int = 120):
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            url = f"{self.base_url}/api2/json/nodes/{node}/tasks/{upid}/status"
            resp = requests.get(
                url,
                headers=self._headers(),
                verify=self.tls_verify,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            if data["status"] == "stopped":
                if data.get("exitstatus") != "OK":
                    raise RuntimeError(f"Task failed: {data.get('exitstatus')}")
                return
            time.sleep(2)
        raise TimeoutError("Timed out waiting for Proxmox task")
