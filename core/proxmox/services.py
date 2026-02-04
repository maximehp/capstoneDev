from .client import ProxmoxClient

_client = None


def _client_instance():
    global _client
    if _client is None:
        _client = ProxmoxClient()
    return _client


def provision_default_vm(node: str, vmid: int):
    client = _client_instance()

    template_vmid = 1002
    vm_name = f"capstone-{vmid}"

    upid = client.clone_from_template(
        node=node,
        template_vmid=template_vmid,
        new_vmid=vmid,
        name=vm_name,
    )

    client.wait_for_task(node=node, upid=upid)

    return client.start_vm(node=node, vmid=vmid)
