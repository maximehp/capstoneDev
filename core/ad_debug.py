import os
from ldap3 import Server, Connection, SIMPLE


def dump_ad_attributes_as_user(username: str, password: str) -> dict:
    host = os.environ["AD_LDAP_HOST"].strip()
    upn_suffix = os.environ["AD_UPN_SUFFIX"].strip()
    base_dn = os.environ["AD_BASE_DN"].strip()

    bind_user = f"{username}@{upn_suffix}"

    server = Server(host)
    conn = Connection(
        server,
        user=bind_user,
        password=password,
        authentication=SIMPLE,
        auto_bind=True,
    )

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

    return {"found": True, "username": username, "attributes": normalized}