import os
from ldap3 import Server, Connection, SIMPLE
from .auth_backends import _candidate_endpoints


def dump_ad_attributes_as_user(username: str, password: str) -> dict:
    host = os.environ.get("AD_LDAP_HOST", "").strip() or os.environ.get("AD_HOST", "").strip()
    upn_suffix = os.environ["AD_UPN_SUFFIX"].strip()
    base_dn = os.environ["AD_BASE_DN"].strip()

    bind_user = f"{username}@{upn_suffix}"
    timeout_raw = os.environ.get("AD_LDAP_CONNECT_TIMEOUT", "5").strip()
    try:
        connect_timeout = float(timeout_raw)
    except ValueError:
        connect_timeout = 5.0

    conn = None
    errors = []
    for endpoint_host, port, use_ssl in _candidate_endpoints(host, upn_suffix):
        server = Server(endpoint_host, port=port, use_ssl=use_ssl, connect_timeout=connect_timeout)
        try:
            conn = Connection(
                server,
                user=bind_user,
                password=password,
                authentication=SIMPLE,
                auto_bind=True,
            )
            break
        except Exception as exc:
            errors.append(f"{endpoint_host}:{port} ssl={use_ssl} -> {exc}")

    if conn is None:
        return {
            "found": False,
            "username": username,
            "attributes": {},
            "error": "AD bind failed",
            "endpoints": errors,
        }

    conn.search(
        search_base=base_dn,
        search_filter=f"(sAMAccountName={username})",
        attributes=["*", "+"],
        size_limit=1,
    )

    if not conn.entries:
        return {"found": False, "username": username, "attributes": {}}

    entry = conn.entries[0]
    data = entry.entry_attributes_as_dict

    normalized = {}
    for key, value in data.items():
        if isinstance(value, list):
            normalized[key] = [str(v) for v in value]
        else:
            normalized[key] = str(value)

    conn.unbind()
    return {"found": True, "username": username, "attributes": normalized}
