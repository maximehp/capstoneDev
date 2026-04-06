from django.contrib import admin

from .models import IsoSource, SoftwareSource, TemplateBuildJob, TemplateDefinition, VirtualMachine


@admin.register(IsoSource)
class IsoSourceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "filename", "url", "last_seen_at")
    search_fields = ("url", "filename", "label", "user__username")


@admin.register(SoftwareSource)
class SoftwareSourceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "filename", "url", "last_seen_at")
    search_fields = ("url", "filename", "label", "user__username")


@admin.register(TemplateDefinition)
class TemplateDefinitionAdmin(admin.ModelAdmin):
    list_display = ("id", "template_name", "build_profile", "template_vmid", "target_os", "owner", "updated_at")
    search_fields = ("template_name", "template_vmid", "build_profile", "owner__username")


@admin.register(TemplateBuildJob)
class TemplateBuildJobAdmin(admin.ModelAdmin):
    list_display = ("id", "uuid", "template_definition", "status", "stage", "created_at")
    search_fields = ("uuid", "template_definition__template_name", "owner__username")


@admin.register(VirtualMachine)
class VirtualMachineAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "proxmox_vmid", "status", "node", "owner", "created_at")
    search_fields = ("name", "proxmox_vmid", "template_definition__template_name", "owner__username")
