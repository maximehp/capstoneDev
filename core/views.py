import json
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .proxmox import services as proxmox_services


def _wants_fragment(request) -> bool:
    return request.headers.get("X-Requested-With") in {"fetch", "prefetch"}


def _extract_content_only(full_html: str) -> str:
    """
    Extracts the inner HTML of <main id="app-content">...</main>.
    This avoids a second template and keeps your existing pages unchanged.
    """
    marker_start = '<main id="app-content"'
    idx = full_html.find(marker_start)
    if idx == -1:
        return full_html

    idx = full_html.find(">", idx)
    if idx == -1:
        return full_html

    end = full_html.find("</main>", idx)
    if end == -1:
        return full_html

    return full_html[idx + 1:end]


def home(request):
    context = {}
    if _wants_fragment(request):
        html = render(request, "home.html", context=context).content.decode("utf-8")
        title = "Capstone Home"
        return JsonResponse({"title": title, "html": _extract_content_only(html)}, status=200)
    return render(request, "home.html", context=context)


def settings(request):
    context = {}
    if _wants_fragment(request):
        html = render(request, "settings.html", context=context).content.decode("utf-8")
        title = "Capstone Settings"
        return JsonResponse({"title": title, "html": _extract_content_only(html)}, status=200)
    return render(request, "settings.html", context=context)


@require_POST
@csrf_protect
def start_vm(request):
    payload = json.loads(request.body.decode("utf-8") or "{}")

    node = payload.get("node", "Kif")
    vmid = int(payload.get("vm_id", 900))

    data = proxmox_services.provision_default_vm(node=node, vmid=vmid)

    return JsonResponse({"ok": True, "data": data})
