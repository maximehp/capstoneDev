
import ipaddress
import json
import re
import socket
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.contrib.admin.utils import unquote
from django.contrib.auth import authenticate, login as django_login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .models import IsoSource, SoftwareSource, TemplateBuildJob, TemplateDefinition
from .packer_profiles import (
    BUILD_PROFILE_CHOICES,
    BUILD_PROFILE_DEBIAN_PRESEED,
    BUILD_PROFILE_UBUNTU_AUTOINSTALL,
    BUILD_PROFILE_WINDOWS_UNATTEND,
    WINDOWS_FIRMWARE_BIOS_LEGACY,
    WINDOWS_FIRMWARE_CHOICES,
    WINDOWS_IMAGE_SELECTOR_CHOICES,
    WINDOWS_IMAGE_SELECTOR_INDEX,
    WINDOWS_IMAGE_SELECTOR_NAME,
    target_os_for_profile,
)
from .proxmox import services as proxmox_services
from .template_builds import build_job_api_payload, enqueue_template_build, template_creation_allowed


def _wants_fragment(request) -> bool:
    return request.headers.get("X-Requested-With") in {"fetch", "prefetch"}


EXTRACTORS = {
    "content": {
        "open": '<main id="app-content"',
        "close": "</main>",
        "fallback": None,
    },
    "head": {
        "open": '<div id="extra-head"',
        "close": "</div>",
        "fallback": "",
    },
    "scripts": {
        "open": '<div id="extra-scripts"',
        "close": "</div>",
        "fallback": "",
    },
}


_PACKAGE_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]{0,63}$")
_INSTALL_STRATEGIES = {"package_manager", "native_installer", "archive", "script", "custom_command"}
_WINDOWS_NATIVE = {"exe", "msi", "msix"}
_WINDOWS_ALLOWED = {"exe", "msi", "msix", "zip", "ps1", "bat", "cmd", "unknown", "bin"}
_LINUX_ALLOWED = {"deb", "rpm", "apk", "tar", "zip", "sh", "run", "bin", "unknown"}
_DEFAULT_WINDOWS_SILENT_ARGS = "/quiet /norestart"
_BUILD_PROFILE_VALUES = {choice[0] for choice in BUILD_PROFILE_CHOICES}
_WINDOWS_FIRMWARE_VALUES = {choice[0] for choice in WINDOWS_FIRMWARE_CHOICES}
_WINDOWS_IMAGE_SELECTOR_VALUES = {choice[0] for choice in WINDOWS_IMAGE_SELECTOR_CHOICES}


def extract_region(full_html: str, key: str) -> str:
    cfg = EXTRACTORS[key]

    fallback = full_html if cfg["fallback"] is None else cfg["fallback"]

    idx = full_html.find(cfg["open"])
    if idx == -1:
        return fallback

    idx = full_html.find(">", idx)
    if idx == -1:
        return fallback

    end = full_html.find(cfg["close"], idx)
    if end == -1:
        return fallback

    return full_html[idx + 1:end]


def home(request):
    context = {}

    if _wants_fragment(request):
        html = render(request, "home.html", context=context).content.decode("utf-8")
        return JsonResponse(
            {
                "title": "Capstone Home",
                "head": extract_region(html, "head"),
                "html": extract_region(html, "content"),
                "scripts": extract_region(html, "scripts"),
            },
            status=200,
        )

    return render(request, "home.html", context=context)


def settings(request):
    context = {}

    if _wants_fragment(request):
        html = render(request, "settings.html", context=context).content.decode("utf-8")
        return JsonResponse(
            {
                "title": "Capstone Settings",
                "head": extract_region(html, "head"),
                "html": extract_region(html, "content"),
                "scripts": extract_region(html, "scripts"),
            },
            status=200,
        )

    return render(request, "settings.html", context=context)


def _wants_json(request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


@csrf_protect
def login_view(request):
    if request.method == "POST" and _wants_json(request):
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

        username = payload.get("username", "").strip()
        password = payload.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is None:
            return JsonResponse(
                {"ok": False, "error": "Invalid username or password"},
                status=401,
            )

        django_login(request, user)

        return JsonResponse({"ok": True, "redirect": "/"}, status=200)

    return render(request, "login.html")


@require_POST
@login_required
@csrf_protect
def start_vm(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    node = str(payload.get("node", "Kif") or "Kif").strip()
    try:
        vmid = int(payload.get("vm_id", 900))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "vm_id must be an integer"}, status=400)

    try:
        data = proxmox_services.provision_default_vm(
            node=node,
            vmid=vmid,
        )
    except Exception as exc:
        return JsonResponse({"ok": False, "error": f"Proxmox request failed: {exc}"}, status=502)

    return JsonResponse(
        {
            "ok": True,
            "data": data,
        }
    )

def _is_public_hostname(hostname: str) -> bool:
    if getattr(settings, "ALLOW_PRIVATE_TEMPLATE_ASSET_URLS", True):
        return True

    if not hostname:
        return False

    hostname = hostname.strip().lower()

    if hostname in {"localhost", "localhost.localdomain"}:
        return False

    try:
        ip = ipaddress.ip_address(hostname)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        return False

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False

    return True


def _filename_from_headers_or_url(headers: dict, url: str) -> str:
    cd = headers.get("Content-Disposition") or headers.get("content-disposition") or ""
    if cd:
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.IGNORECASE)
        if m:
            return unquote(m.group(1)).split("/")[-1]

    path = urlparse(url).path
    name = path.split("/")[-1].strip()
    return name or "unknown.bin"


def _inspect_url(raw_url: str, require_iso: bool) -> dict:
    if not raw_url:
        raise ValueError("Missing url parameter")

    try:
        parsed = urlparse(raw_url)
    except Exception:
        raise ValueError("Invalid URL")

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are allowed")

    if not _is_public_hostname(parsed.hostname or ""):
        raise ValueError("URL host is not allowed")

    timeout = (4, 8)
    headers = {
        "User-Agent": "capstoneDev/iso-inspect",
        "Accept": "*/*",
    }

    res = requests.head(raw_url, allow_redirects=True, timeout=timeout, headers=headers)
    if res.status_code >= 400:
        raise RuntimeError("HTTP " + str(res.status_code))

    final_url = res.url
    h = dict(res.headers)

    content_type = h.get("Content-Type", "") or h.get("content-type", "")
    last_modified = h.get("Last-Modified", "") or h.get("last-modified", "")
    length = h.get("Content-Length", "") or h.get("content-length", "")

    size_bytes = None
    if length and length.isdigit():
        size_bytes = int(length)

    if size_bytes is None:
        get_headers = dict(headers)
        get_headers["Range"] = "bytes=0-0"
        r2 = requests.get(raw_url, allow_redirects=True, timeout=timeout, headers=get_headers, stream=True)
        if r2.status_code in {200, 206}:
            h2 = dict(r2.headers)
            cr = h2.get("Content-Range", "") or h2.get("content-range", "")
            m = re.search(r"/(\d+)$", cr)
            if m:
                size_bytes = int(m.group(1))

            if not content_type:
                content_type = h2.get("Content-Type", "") or h2.get("content-type", "")
            if not last_modified:
                last_modified = h2.get("Last-Modified", "") or h2.get("last-modified", "")

    filename = _filename_from_headers_or_url(h, final_url)

    if require_iso and not filename.lower().endswith(".iso"):
        raise ValueError("URL does not look like a direct .iso download")

    return {
        "final_url": final_url,
        "filename": filename,
        "size_bytes": size_bytes,
        "content_type": content_type or None,
        "last_modified": last_modified or None,
    }


def _record_source(model, user, url: str, filename: str, content_type: str, size_bytes, last_modified: str):
    if not user or not user.is_authenticated:
        return None

    defaults = {
        "filename": filename or "",
        "content_type": content_type or "",
        "size_bytes": size_bytes,
        "last_modified": last_modified or "",
        "last_seen_at": timezone.now(),
    }

    obj, _ = model.objects.update_or_create(
        user=user,
        url=url,
        defaults=defaults,
    )
    return obj


@require_GET
@login_required
def iso_inspect(request):
    raw_url = request.GET.get("url", "").strip()
    if not raw_url:
        return JsonResponse({"ok": False, "error": "Missing url parameter"}, status=400)

    try:
        data = _inspect_url(raw_url=raw_url, require_iso=True)
        _record_source(
            model=IsoSource,
            user=request.user,
            url=raw_url,
            filename=data.get("filename") or "",
            content_type=data.get("content_type") or "",
            size_bytes=data.get("size_bytes"),
            last_modified=data.get("last_modified") or "",
        )
        return JsonResponse(
            {
                "ok": True,
                "final_url": data.get("final_url"),
                "filename": data.get("filename"),
                "size_bytes": data.get("size_bytes"),
                "content_type": data.get("content_type"),
                "last_modified": data.get("last_modified"),
            }
        )

    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@require_GET
@login_required
def software_inspect(request):
    raw_url = request.GET.get("url", "").strip()
    if not raw_url:
        return JsonResponse({"ok": False, "error": "Missing url parameter"}, status=400)

    try:
        data = _inspect_url(raw_url=raw_url, require_iso=False)
        _record_source(
            model=SoftwareSource,
            user=request.user,
            url=raw_url,
            filename=data.get("filename") or "",
            content_type=data.get("content_type") or "",
            size_bytes=data.get("size_bytes"),
            last_modified=data.get("last_modified") or "",
        )
        return JsonResponse(
            {
                "ok": True,
                "final_url": data.get("final_url"),
                "filename": data.get("filename"),
                "size_bytes": data.get("size_bytes"),
                "content_type": data.get("content_type"),
                "last_modified": data.get("last_modified"),
            }
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@require_GET
@login_required
def iso_saved(request):
    items = (
        IsoSource.objects
        .filter(user=request.user)
        .order_by("-last_seen_at")[:50]
    )
    payload = []
    for item in items:
        payload.append(
            {
                "id": item.id,
                "label": item.label or "",
                "url": item.url,
                "filename": item.filename,
                "content_type": item.content_type,
                "size_bytes": item.size_bytes,
                "last_modified": item.last_modified,
                "last_seen_at": item.last_seen_at.isoformat(),
            }
        )
    return JsonResponse({"ok": True, "items": payload})


@require_GET
@login_required
def software_saved(request):
    items = (
        SoftwareSource.objects
        .filter(user=request.user)
        .order_by("-last_seen_at")[:50]
    )
    payload = []
    for item in items:
        payload.append(
            {
                "id": item.id,
                "label": item.label or "",
                "url": item.url,
                "filename": item.filename,
                "content_type": item.content_type,
                "size_bytes": item.size_bytes,
                "last_modified": item.last_modified,
                "last_seen_at": item.last_seen_at.isoformat(),
            }
        )
    return JsonResponse({"ok": True, "items": payload})

def _normalize_url_list(items):
    if not isinstance(items, list):
        return []

    out = []
    seen = set()
    for item in items:
        if not isinstance(item, str):
            continue
        raw = item.strip()
        if not raw:
            continue
        key = raw.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(raw)
    return out


def _normalize_package_list(items):
    if not isinstance(items, list):
        return []

    out = []
    seen = set()
    for item in items:
        if not isinstance(item, str):
            continue
        token = item.strip().lower()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _artifact_type_from_name(name: str) -> str:
    n = (name or "").lower()
    if n.endswith(".msix"):
        return "msix"
    if n.endswith(".msi"):
        return "msi"
    if n.endswith(".exe"):
        return "exe"
    if n.endswith(".deb"):
        return "deb"
    if n.endswith(".rpm"):
        return "rpm"
    if n.endswith(".apk"):
        return "apk"
    if n.endswith(".tar.gz") or n.endswith(".tgz") or n.endswith(".tar.xz") or n.endswith(".tar.bz2") or n.endswith(".tar"):
        return "tar"
    if n.endswith(".zip"):
        return "zip"
    if n.endswith(".ps1"):
        return "ps1"
    if n.endswith(".bat"):
        return "bat"
    if n.endswith(".cmd"):
        return "cmd"
    if n.endswith(".sh"):
        return "sh"
    if n.endswith(".run"):
        return "run"
    if n.endswith(".bin"):
        return "bin"
    return "unknown"


def _infer_install_strategy(kind: str, artifact_type: str, target_os: str) -> str:
    if kind == "package":
        return "package_manager" if target_os == "linux" else "custom_command"

    if target_os == "windows":
        if artifact_type in _WINDOWS_NATIVE:
            return "native_installer"
        if artifact_type == "zip":
            return "archive"
        if artifact_type in {"ps1", "bat", "cmd"}:
            return "script"
        return "custom_command"

    if artifact_type in {"deb", "rpm", "apk"}:
        return "package_manager"
    if artifact_type in {"tar", "zip"}:
        return "archive"
    if artifact_type in {"sh", "run"}:
        return "script"
    return "custom_command"


def _normalize_software_items(payload: dict):
    items = payload.get("software_items")
    if isinstance(items, list) and items:
        out = []
        seen = set()
        for raw in items:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("kind") or "").lower().strip()
            if kind not in {"url", "package"}:
                continue

            if kind == "url":
                url = str(raw.get("url") or "").strip()
                if not url:
                    continue
                key = ("url", url.lower())
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "kind": "url",
                        "url": url,
                        "label": str(raw.get("label") or "").strip(),
                        "artifact_type": str(raw.get("artifact_type") or "").lower().strip(),
                        "install_strategy": str(raw.get("install_strategy") or "").lower().strip(),
                        "silent_args": str(raw.get("silent_args") or "").strip(),
                    }
                )
                continue

            name = str(raw.get("label") or raw.get("name") or "").strip().lower()
            if not name:
                continue
            key = ("package", name)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "kind": "package",
                    "name": name,
                    "artifact_type": "package",
                    "install_strategy": str(raw.get("install_strategy") or "").lower().strip(),
                    "silent_args": str(raw.get("silent_args") or "").strip(),
                }
            )
        return out

    out = []
    for url in _normalize_url_list(payload.get("software_urls")):
        out.append(
            {
                "kind": "url",
                "url": url,
                "label": "",
                "artifact_type": "",
                "install_strategy": "",
                "silent_args": "",
            }
        )
    for pkg in _normalize_package_list(payload.get("custom_packages")):
        out.append(
            {
                "kind": "package",
                "name": pkg,
                "artifact_type": "package",
                "install_strategy": "",
                "silent_args": "",
            }
        )
    return out


def _validate_template_software_payload(payload: dict) -> dict:
    target_os = str(payload.get("target_os") or "").strip().lower()
    if target_os not in {"linux", "windows"}:
        target_os = ""

    input_items = _normalize_software_items(payload)
    services = payload.get("services") if isinstance(payload.get("services"), dict) else {}

    service_flags = {
        "qemu_guest": bool(services.get("qemu_guest", False)),
        "docker": bool(services.get("docker", False)),
        "devtools": bool(services.get("devtools", False)),
    }

    errors = []
    warnings = []
    software_items = []
    normalized_packages = []

    if not target_os:
        errors.append("Target OS must be selected.")

    for item in input_items:
        if item["kind"] == "package":
            pkg = item["name"]
            if _PACKAGE_RE.fullmatch(pkg) is None:
                errors.append(
                    f"Invalid package name: {pkg}. Use lowercase letters, numbers, +, . or -."
                )
                continue
            if target_os == "windows":
                errors.append(f"Package-manager package is not supported for Windows target: {pkg}")
                continue

            strategy = item.get("install_strategy") or _infer_install_strategy("package", "package", target_os or "linux")
            if strategy not in _INSTALL_STRATEGIES:
                strategy = _infer_install_strategy("package", "package", target_os or "linux")

            normalized_packages.append(pkg)
            software_items.append(
                {
                    "kind": "package",
                    "name": pkg,
                    "label": pkg,
                    "artifact_type": "package",
                    "install_strategy": strategy,
                    "silent_args": "",
                }
            )
            continue

        url = item["url"]
        try:
            inspected = _inspect_url(raw_url=url, require_iso=False)
        except Exception as exc:
            errors.append(f"Software URL failed validation: {url} ({exc})")
            continue

        final_url = inspected.get("final_url") or url
        filename = inspected.get("filename") or ""
        artifact_type = item.get("artifact_type") or _artifact_type_from_name(filename or final_url)
        strategy = item.get("install_strategy") or _infer_install_strategy("url", artifact_type, target_os or "linux")
        if strategy not in _INSTALL_STRATEGIES:
            strategy = _infer_install_strategy("url", artifact_type, target_os or "linux")

        if target_os == "linux" and artifact_type in {"exe", "msi", "msix"}:
            errors.append(f"Incompatible artifact for Linux target: {filename or final_url}")
            continue

        if target_os == "windows" and artifact_type in {"deb", "rpm", "apk", "sh", "run"}:
            errors.append(f"Incompatible artifact for Windows target: {filename or final_url}")
            continue

        if target_os == "windows" and artifact_type not in _WINDOWS_ALLOWED:
            warnings.append(f"Unknown Windows artifact type for {filename or final_url}")
        if target_os == "linux" and artifact_type not in _LINUX_ALLOWED:
            warnings.append(f"Unknown Linux artifact type for {filename or final_url}")

        silent_args = item.get("silent_args") or ""
        if target_os == "windows" and artifact_type in _WINDOWS_NATIVE:
            if not silent_args:
                silent_args = _DEFAULT_WINDOWS_SILENT_ARGS

        software_items.append(
            {
                "id": f"software-{len(software_items) + 1}",
                "kind": "url",
                "url": final_url,
                "label": item.get("label") or filename or final_url,
                "filename": filename,
                "size_bytes": inspected.get("size_bytes"),
                "content_type": inspected.get("content_type"),
                "last_modified": inspected.get("last_modified"),
                "artifact_type": artifact_type,
                "install_strategy": strategy,
                "silent_args": silent_args,
            }
        )

    if not software_items and not any(service_flags.values()):
        warnings.append("No software, packages, or services selected.")

    return {
        "ok": True,
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "normalized": {
            "target_os": target_os,
            "software_urls": [item["url"] for item in software_items if item.get("kind") == "url" and item.get("url")],
            "software_items": software_items,
            "custom_packages": normalized_packages,
            "services": service_flags,
        },
    }

def _coerce_int(raw_value, default: int, minimum: int, maximum: int) -> int:
    try:
        n = int(raw_value)
    except (TypeError, ValueError):
        n = default
    if n < minimum:
        return minimum
    if n > maximum:
        return maximum
    return n


def _normalize_static_dns(raw_dns):
    if isinstance(raw_dns, list):
        out = []
        for item in raw_dns:
            token = str(item).strip()
            if token:
                out.append(token)
        return out
    if isinstance(raw_dns, str):
        return [token.strip() for token in raw_dns.split(",") if token.strip()]
    return []


def _normalize_linux_options(raw_linux: dict) -> dict:
    return {
        "ssh_timeout": str(raw_linux.get("ssh_timeout") or "45m").strip(),
    }


def _normalize_build_profile(payload: dict) -> str:
    build_profile = str(payload.get("build_profile") or "").strip().lower()
    if build_profile in _BUILD_PROFILE_VALUES:
        return build_profile
    return ""


def _validate_windows_payload(payload: dict) -> tuple[dict, list[str]]:
    raw_windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
    try:
        winrm_port = int(raw_windows.get("winrm_port") or 5985)
    except (TypeError, ValueError):
        winrm_port = 5985
    windows = {
        "admin_username": str(raw_windows.get("admin_username") or "").strip(),
        "admin_password": str(raw_windows.get("admin_password") or "").strip(),
        "image_selector_type": str(raw_windows.get("image_selector_type") or WINDOWS_IMAGE_SELECTOR_NAME).strip().lower(),
        "image_selector_value": str(raw_windows.get("image_selector_value") or "").strip(),
        "virtio_iso_url": str(raw_windows.get("virtio_iso_url") or "").strip(),
        "firmware_profile": str(raw_windows.get("firmware_profile") or WINDOWS_FIRMWARE_BIOS_LEGACY).strip().lower(),
        "winrm_port": winrm_port,
        "winrm_use_ssl": bool(raw_windows.get("winrm_use_ssl", False)),
        "winrm_timeout": str(raw_windows.get("winrm_timeout") or "2h").strip(),
    }

    errors = []
    required_fields = {
        "admin_username": "Windows admin username is required.",
        "admin_password": "Windows admin password is required.",
        "image_selector_value": "Windows image selector value is required.",
        "virtio_iso_url": "Windows VirtIO ISO URL is required.",
    }
    for key, message in required_fields.items():
        if not windows[key]:
            errors.append(message)

    if windows["image_selector_type"] not in _WINDOWS_IMAGE_SELECTOR_VALUES:
        errors.append("Windows image selector type is invalid.")

    if windows["firmware_profile"] not in _WINDOWS_FIRMWARE_VALUES:
        errors.append("Windows firmware profile is invalid.")

    for url_key in ["virtio_iso_url"]:
        if windows[url_key]:
            try:
                _inspect_url(raw_url=windows[url_key], require_iso=True)
            except Exception as exc:
                errors.append(f"Invalid Windows {url_key.replace('_', ' ')}: {exc}")

    return windows, errors


@require_POST
@login_required
@csrf_protect
def validate_template_software(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    return JsonResponse(_validate_template_software_payload(payload))


@require_POST
@login_required
@csrf_protect
def create_template_definition(request):
    if not template_creation_allowed(request.user):
        return JsonResponse(
            {
                "ok": False,
                "error": "Only faculty can create templates.",
            },
            status=403,
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    build_profile = _normalize_build_profile(payload)
    if not build_profile:
        return JsonResponse({"ok": False, "error": "Build profile is required."}, status=400)

    target_os = target_os_for_profile(build_profile)
    requested_target_os = str(payload.get("target_os") or "").strip().lower()
    if requested_target_os and requested_target_os != target_os:
        return JsonResponse({"ok": False, "error": "Target OS does not match selected build profile."}, status=400)

    template_name = str(payload.get("template_name") or "").strip()
    if not template_name:
        return JsonResponse({"ok": False, "error": "Template name is required."}, status=400)

    iso_url = str(payload.get("iso_url") or "").strip()
    if not iso_url:
        return JsonResponse({"ok": False, "error": "ISO URL is required."}, status=400)

    try:
        iso_info = _inspect_url(raw_url=iso_url, require_iso=True)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": f"ISO validation failed: {exc}"}, status=400)

    validation = _validate_template_software_payload(payload)
    if validation.get("valid") is not True:
        return JsonResponse(
            {
                "ok": False,
                "error": "Software validation failed.",
                "validation": validation,
            },
            status=400,
        )

    normalized = validation.get("normalized", {})
    if normalized.get("target_os") and normalized.get("target_os") != target_os:
        return JsonResponse({"ok": False, "error": "Software target OS does not match build profile."}, status=400)
    normalized["target_os"] = target_os
    normalized["build_profile"] = build_profile

    hw_raw = payload.get("hardware") if isinstance(payload.get("hardware"), dict) else {}
    net_raw = payload.get("network") if isinstance(payload.get("network"), dict) else {}

    hardware = {
        "cpu": _coerce_int(hw_raw.get("cpu", 2), 2, 1, 64),
        "ram_gb": _coerce_int(hw_raw.get("ram_gb", 4), 4, 1, 512),
        "disk_gb": _coerce_int(hw_raw.get("disk_gb", 32), 32, 8, 4096),
    }

    vlan_raw = net_raw.get("vlan")
    vlan = None
    if vlan_raw not in {"", None}:
        vlan = _coerce_int(vlan_raw, 1, 1, 4094)

    ipv4_mode = str(net_raw.get("ipv4_mode") or "dhcp").lower()
    if ipv4_mode not in {"dhcp", "static"}:
        ipv4_mode = "dhcp"

    network = {
        "bridge": str(net_raw.get("bridge") or ""),
        "vlan": vlan,
        "ipv4_mode": ipv4_mode,
        "static_ip": str(net_raw.get("static_ip") or "").strip(),
        "static_gateway": str(net_raw.get("static_gateway") or "").strip(),
        "static_dns": _normalize_static_dns(net_raw.get("static_dns")),
    }
    if network["ipv4_mode"] != "dhcp" or network["static_ip"] or network["static_gateway"] or network["static_dns"]:
        return JsonResponse(
            {
                "ok": False,
                "error": "Static networking is not supported for template builds. Templates must remain DHCP-ready.",
            },
            status=400,
        )
    if not network["bridge"]:
        return JsonResponse({"ok": False, "error": "Network bridge is required."}, status=400)

    linux_raw = payload.get("linux") if isinstance(payload.get("linux"), dict) else {}
    linux = _normalize_linux_options(linux_raw)

    windows = {}
    if target_os == TemplateDefinition.TARGET_OS_WINDOWS:
        windows, windows_errors = _validate_windows_payload(payload)
        if windows_errors:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Windows options are invalid.",
                    "errors": windows_errors,
                },
                status=400,
            )

    template_vmid = f"100{request.user.id}"
    if TemplateDefinition.objects.filter(owner=request.user, template_vmid=template_vmid).exists():
        return JsonResponse(
            {
                "ok": False,
                "error": f"Template VMID collision: {template_vmid} already exists for this account.",
            },
            status=409,
        )

    ansible_options = payload.get("ansible") if isinstance(payload.get("ansible"), dict) else {}

    build_payload = {
        "template_name": template_name,
        "template_vmid": template_vmid,
        "build_profile": build_profile,
        "target_os": target_os,
        "iso_url": iso_info.get("final_url") or iso_url,
        "iso_filename": iso_info.get("filename"),
        "iso_size_bytes": iso_info.get("size_bytes"),
        "software_urls": normalized.get("software_urls", []),
        "software_items": normalized.get("software_items", []),
        "custom_packages": normalized.get("custom_packages", []),
        "services": normalized.get("services", {}),
        "hardware": hardware,
        "network": network,
        "linux": linux,
        "windows": windows,
        "ansible": ansible_options,
        "generated_at": timezone.now().isoformat(),
        "guest_networking": "dhcp",
    }

    template_definition = TemplateDefinition.objects.create(
        owner=request.user,
        template_name=template_name,
        template_vmid=template_vmid,
        build_profile=build_profile,
        target_os=target_os,
        iso_url=build_payload["iso_url"],
        iso_filename=build_payload.get("iso_filename") or "",
        iso_size_bytes=build_payload.get("iso_size_bytes"),
        normalized_payload=normalized,
        hardware=hardware,
        network=network,
        windows_options=windows,
        ansible_options=ansible_options,
    )

    try:
        job = enqueue_template_build(template_definition=template_definition, payload_snapshot=build_payload)
    except Exception as exc:
        template_definition.delete()
        return JsonResponse(
            {
                "ok": False,
                "error": f"Failed to queue template build job: {exc}",
            },
            status=500,
        )

    return JsonResponse(
        {
            "ok": True,
            "template": {
                "id": template_definition.id,
                "name": template_definition.template_name,
                "vmid": template_definition.template_vmid,
                "target_os": template_definition.target_os,
                "build_profile": template_definition.build_profile,
            },
            "job": {
                "id": str(job.uuid),
                "status": job.status,
                "stage": job.stage,
            },
            "warnings": validation.get("warnings", []),
            "normalized": normalized,
        },
        status=202,
    )


@require_GET
@login_required
def template_build_status(request, job_uuid):
    job = (
        TemplateBuildJob.objects
        .select_related("template_definition")
        .filter(uuid=job_uuid, owner=request.user)
        .first()
    )
    if not job:
        return JsonResponse({"ok": False, "error": "Build job not found."}, status=404)

    return JsonResponse({"ok": True, "job": build_job_api_payload(job)}, status=200)
