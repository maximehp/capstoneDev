from django.http import JsonResponse
from django.shortcuts import render

def _wants_fragment(request) -> bool:
    return request.headers.get("X-Requested-With") in {"fetch", "prefetch"}

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
