"""
URL configuration for capstoneDev project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", views.home, name="home"),
    path("settings/", views.settings, name="settings"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("api/vm/start/", views.start_vm, name="start_vm"),
    path("api/iso/inspect", views.iso_inspect, name="iso_inspect_no_slash"),
    path("api/iso/inspect/", views.iso_inspect, name="iso_inspect"),
    path("api/software/inspect", views.software_inspect, name="software_inspect_no_slash"),
    path("api/software/inspect/", views.software_inspect, name="software_inspect"),
    path("api/iso/saved/", views.iso_saved, name="iso_saved"),
    path("api/software/saved/", views.software_saved, name="software_saved"),
    path(
        "api/template/validate-software/",
        views.validate_template_software,
        name="validate_template_software",
    ),
    path(
        "api/template/create/",
        views.create_template_definition,
        name="create_template_definition",
    ),
    path(
        "api/template/builds/<uuid:job_uuid>/status/",
        views.template_build_status,
        name="template_build_status",
    ),
]
