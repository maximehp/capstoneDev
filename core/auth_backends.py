import os
import logging
import ipaddress
import socket
from ldap3 import Server, Connection, SIMPLE
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from .models import DirectoryProfile

logger = logging.getLogger(__name__)
_LAST_SUCCESS_ENDPOINT: tuple[str, int, bool] | None = None


def _parse_host_port(host_value: str) -> tuple[str, int | None]:
    host = (host_value or "").strip()
    if not host:
        return "", None

    if "://" in host:
        host = host.split("://", 1)[1]

    if host.startswith("[") and "]:" in host:
        base, port_raw = host.rsplit("]:", 1)
        try:
            return base.strip("[]"), int(port_raw)
        except ValueError:
            return base.strip("[]"), None

    if host.count(":") == 1:
        base, port_raw = host.rsplit(":", 1)
        try:
            return base, int(port_raw)
        except ValueError:
            return host, None

    return host, None


def _split_hosts(raw_hosts: str) -> list[str]:
    parts = []
    for piece in (raw_hosts or "").replace(";", ",").split(","):
        value = piece.strip()
        if value:
            parts.append(value)
    return parts


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _host_variants(host: str) -> list[str]:
    if _is_ip_address(host):
        return [host]

    try:
        addrinfos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except Exception:
        return [host]

    variants = []
    for info in addrinfos:
        ip = info[4][0]
        if ip not in variants:
            variants.append(ip)

    return variants or [host]


def _connection_modes(parsed_port: int | None) -> list[tuple[int, bool]]:
    forced_port_raw = os.environ.get("AD_LDAP_PORT", "").strip()
    forced_ssl_raw = os.environ.get("AD_LDAP_USE_SSL", "").strip().lower()

    forced_ssl: bool | None = None
    if forced_ssl_raw:
        forced_ssl = forced_ssl_raw in {"1", "true", "yes", "on"}

    if parsed_port is not None:
        use_ssl = forced_ssl if forced_ssl is not None else parsed_port == 636
        return [(parsed_port, use_ssl)]

    if forced_port_raw:
        try:
            forced_port = int(forced_port_raw)
        except ValueError:
            forced_port = 389
        use_ssl = forced_ssl if forced_ssl is not None else forced_port == 636
        return [(forced_port, use_ssl)]

    if forced_ssl is True:
        return [(636, True)]
    if forced_ssl is False:
        return [(389, False)]

    # Default to LDAP only. Enable LDAPS explicitly with AD_LDAP_USE_SSL/AD_LDAP_PORT.
    return [(389, False)]


def _candidate_endpoints(dc_host: str, upn_suffix: str) -> list[tuple[str, int, bool]]:
    raw_hosts = _split_hosts(dc_host)
    if not raw_hosts and upn_suffix:
        raw_hosts = [upn_suffix]

    # If the configured host is a single IP, also try the AD domain as fallback.
    if len(raw_hosts) == 1 and _is_ip_address(_parse_host_port(raw_hosts[0])[0]) and upn_suffix:
        if upn_suffix not in raw_hosts:
            raw_hosts = [upn_suffix, raw_hosts[0]]

    endpoints = []
    seen = set()
    for raw_host in raw_hosts:
        host, parsed_port = _parse_host_port(raw_host)
        if not host:
            continue

        for host_candidate in _host_variants(host):
            for port, use_ssl in _connection_modes(parsed_port):
                key = (host_candidate, port, use_ssl)
                if key in seen:
                    continue
                seen.add(key)
                endpoints.append(key)
    return endpoints


def _prioritize_last_success(endpoints: list[tuple[str, int, bool]]) -> list[tuple[str, int, bool]]:
    if not endpoints:
        return endpoints
    if _LAST_SUCCESS_ENDPOINT not in endpoints:
        return endpoints

    prioritized = [_LAST_SUCCESS_ENDPOINT]
    for endpoint in endpoints:
        if endpoint != _LAST_SUCCESS_ENDPOINT:
            prioritized.append(endpoint)
    return prioritized


def _normalize_ad_attributes(entry_attributes: dict) -> dict:
    normalized = {}
    for key, value in (entry_attributes or {}).items():
        if isinstance(value, list):
            normalized[key] = [str(v) for v in value]
        elif value in {None, ""}:
            normalized[key] = []
        else:
            normalized[key] = [str(value)]
    return normalized


def _first_attr(attributes: dict, key: str) -> str:
    values = attributes.get(key) or []
    return str(values[0]).strip() if values else ""


def _extract_sid_rid(sid: str) -> int | None:
    parts = [part for part in str(sid or "").split("-") if part]
    if not parts:
        return None
    try:
        return int(parts[-1])
    except ValueError:
        return None


def _directory_role(attributes: dict) -> str:
    distinguished_name = _first_attr(attributes, "distinguishedName").lower()
    member_of = [str(item).lower() for item in (attributes.get("memberOf") or [])]

    if "ou=faculty" in distinguished_name:
        return DirectoryProfile.ROLE_FACULTY
    if "ou=students" in distinguished_name:
        return DirectoryProfile.ROLE_STUDENT

    faculty_markers = ["cn=domain admins", "cn=enterprise admins", "cn=schema admins", "cn=administrators"]
    if any(marker in group for marker in faculty_markers for group in member_of):
        return DirectoryProfile.ROLE_FACULTY
    if any("cn=students" in group for group in member_of):
        return DirectoryProfile.ROLE_STUDENT
    return DirectoryProfile.ROLE_UNKNOWN


def _sync_user_from_ad(username: str, attributes: dict):
    object_sid = _first_attr(attributes, "objectSid")
    ad_rid = _extract_sid_rid(object_sid)

    User = get_user_model()
    user, _ = User.objects.get_or_create(username=username)
    user.first_name = _first_attr(attributes, "givenName")
    user.last_name = _first_attr(attributes, "sn")
    user.email = _first_attr(attributes, "userPrincipalName")
    user.is_staff = _directory_role(attributes) == DirectoryProfile.ROLE_FACULTY
    user.save(update_fields=["first_name", "last_name", "email", "is_staff"])

    if object_sid and ad_rid is not None:
        DirectoryProfile.objects.update_or_create(
            user=user,
            defaults={
                "ad_object_sid": object_sid,
                "ad_rid": ad_rid,
                "display_name": _first_attr(attributes, "displayName"),
                "distinguished_name": _first_attr(attributes, "distinguishedName"),
                "user_principal_name": _first_attr(attributes, "userPrincipalName"),
                "department": _first_attr(attributes, "department"),
                "company": _first_attr(attributes, "company"),
                "directory_role": _directory_role(attributes),
                "raw_attributes": attributes,
            },
        )

    return user


def _fetch_ad_attributes(conn, base_dn: str, username: str) -> dict:
    if not base_dn:
        return {}

    try:
        conn.search(
            search_base=base_dn,
            search_filter=f"(sAMAccountName={username})",
            attributes=[
                "objectSid",
                "displayName",
                "givenName",
                "sn",
                "distinguishedName",
                "memberOf",
                "userPrincipalName",
                "department",
                "company",
            ],
            size_limit=1,
        )
        entries = getattr(conn, "entries", None)
        if not entries:
            return {}
        first_entry = entries[0]
        return _normalize_ad_attributes(first_entry.entry_attributes_as_dict)
    except Exception as exc:
        logger.warning("AD attribute sync skipped for %s: %s", username, exc)
        return {}


class ActiveDirectoryBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        global _LAST_SUCCESS_ENDPOINT

        if not username or not password:
            return None

        dc_host = os.environ.get("AD_LDAP_HOST", "").strip() or os.environ.get("AD_HOST", "").strip()
        upn_suffix = os.environ.get("AD_UPN_SUFFIX", "").strip()
        base_dn = os.environ.get("AD_BASE_DN", "").strip()
        timeout_raw = os.environ.get("AD_LDAP_CONNECT_TIMEOUT", "1").strip()
        try:
            connect_timeout = float(timeout_raw)
        except ValueError:
            connect_timeout = 1.0

        if not dc_host or not upn_suffix:
            logger.error("AD_LDAP_HOST or AD_UPN_SUFFIX not set")
            return None

        bind_user = f"{username}@{upn_suffix}"
        errors = []
        connected = False
        credential_rejected = False
        directory_attributes = {}
        endpoints = _prioritize_last_success(_candidate_endpoints(dc_host, upn_suffix))
        for host, port, use_ssl in endpoints:
            server = Server(host, port=port, use_ssl=use_ssl, connect_timeout=connect_timeout)
            try:
                conn = Connection(
                    server,
                    user=bind_user,
                    password=password,
                    authentication=SIMPLE,
                    auto_bind=False,
                )
                if conn.bind():
                    directory_attributes = _fetch_ad_attributes(conn, base_dn=base_dn, username=username)
                    conn.unbind()
                    connected = True
                    _LAST_SUCCESS_ENDPOINT = (host, port, use_ssl)
                    break

                description = (conn.result or {}).get("description", "bind failed")
                message = f"{host}:{port} ssl={use_ssl} -> {description}"
                errors.append(message)
                conn.unbind()
                if str(description).lower() == "invalidcredentials":
                    credential_rejected = True
                    break
            except Exception as exc:
                errors.append(f"{host}:{port} ssl={use_ssl} -> {exc}")

        if not connected:
            logger.warning("AD SIMPLE bind failed for %s: %s", bind_user, " | ".join(errors))
            if credential_rejected:
                logger.info("AD credential rejection for %s occurred on first reachable controller.", bind_user)
            return None

        return _sync_user_from_ad(username=username, attributes=directory_attributes)

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
