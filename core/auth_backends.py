import os
import logging
import ipaddress
import socket
from ldap3 import Server, Connection, SIMPLE
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

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


class ActiveDirectoryBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        global _LAST_SUCCESS_ENDPOINT

        if not username or not password:
            return None

        dc_host = os.environ.get("AD_LDAP_HOST", "").strip() or os.environ.get("AD_HOST", "").strip()
        upn_suffix = os.environ.get("AD_UPN_SUFFIX", "").strip()
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

        User = get_user_model()
        user, _ = User.objects.get_or_create(username=username)
        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
