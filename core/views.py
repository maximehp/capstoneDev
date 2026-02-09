from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth import authenticate, login as django_login
from django.http import JsonResponse
from django.shortcuts import render

import json

from .ad_debug import dump_ad_attributes_as_user
from .proxmox import services as proxmox_services


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

        response = {"ok": True, "redirect": "/"}

        try:
            response["ad_dump"] = dump_ad_attributes_as_user(
                username=username,
                password=password,
            )
        except Exception as exc:
            response["ad_dump_error"] = str(exc)

        return JsonResponse(response, status=200)

    return render(request, "login.html")


@require_POST
@csrf_protect
def start_vm(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")

    node = payload.get("node", "Kif")
    vmid = int(payload.get("vm_id", 900))

    data = proxmox_services.provision_default_vm(
        node=node,
        vmid=vmid,
    )

    return JsonResponse(
        {
            "ok": True,
            "data": data,
        }
    )