from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone

from .packer_profiles import BUILD_PROFILE_CHOICES


class IsoSource(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    url = models.URLField(max_length=512)
    filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    last_modified = models.CharField(max_length=255, blank=True)
    label = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user", "url"])]
        unique_together = [("user", "url")]

    def __str__(self) -> str:
        return self.label or self.filename or self.url


class SoftwareSource(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    url = models.URLField(max_length=512)
    filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    last_modified = models.CharField(max_length=255, blank=True)
    label = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user", "url"])]
        unique_together = [("user", "url")]

    def __str__(self) -> str:
        return self.label or self.filename or self.url


class TemplateDefinition(models.Model):
    TARGET_OS_LINUX = "linux"
    TARGET_OS_WINDOWS = "windows"
    TARGET_OS_CHOICES = [
        (TARGET_OS_LINUX, "Linux"),
        (TARGET_OS_WINDOWS, "Windows"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="template_definitions",
    )
    template_name = models.CharField(max_length=128)
    template_vmid = models.CharField(max_length=32)
    build_profile = models.CharField(max_length=32, choices=BUILD_PROFILE_CHOICES, default="ubuntu_autoinstall")
    target_os = models.CharField(max_length=16, choices=TARGET_OS_CHOICES)
    iso_url = models.URLField(max_length=512)
    iso_filename = models.CharField(max_length=255, blank=True)
    iso_size_bytes = models.BigIntegerField(null=True, blank=True)

    normalized_payload = models.JSONField(default=dict)
    hardware = models.JSONField(default=dict)
    network = models.JSONField(default=dict)
    windows_options = models.JSONField(default=dict)
    ansible_options = models.JSONField(default=dict)

    last_job = models.ForeignKey(
        "TemplateBuildJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "template_vmid"]),
            models.Index(fields=["target_os", "updated_at"]),
        ]
        unique_together = [("owner", "template_vmid")]

    def __str__(self) -> str:
        return f"{self.template_name} ({self.template_vmid})"


class TemplateBuildJob(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELED, "Canceled"),
    ]

    STAGE_QUEUED = "queued"
    STAGE_PREFLIGHT = "preflight"
    STAGE_INIT = "init"
    STAGE_VALIDATE = "validate"
    STAGE_BUILD = "build"
    STAGE_POSTPROCESS = "postprocess"
    STAGE_SEALING = "sealing"
    STAGE_DONE = "done"

    STAGE_CHOICES = [
        (STAGE_QUEUED, "Queued"),
        (STAGE_PREFLIGHT, "Preflight"),
        (STAGE_INIT, "Init"),
        (STAGE_VALIDATE, "Validate"),
        (STAGE_BUILD, "Build"),
        (STAGE_POSTPROCESS, "Postprocess"),
        (STAGE_SEALING, "Sealing"),
        (STAGE_DONE, "Done"),
    ]

    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="template_build_jobs",
    )
    template_definition = models.ForeignKey(
        TemplateDefinition,
        on_delete=models.CASCADE,
        related_name="build_jobs",
    )

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    stage = models.CharField(max_length=16, choices=STAGE_CHOICES, default=STAGE_QUEUED)

    payload_snapshot = models.JSONField(default=dict)
    result_payload = models.JSONField(default=dict)

    workspace_path = models.TextField(blank=True)
    log_path = models.TextField(blank=True)
    packer_template_path = models.TextField(blank=True)

    exit_code = models.IntegerField(null=True, blank=True)
    error_summary = models.TextField(blank=True)

    queued_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "queued_at"]),
            models.Index(fields=["owner", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"TemplateBuildJob<{self.uuid}> {self.status}/{self.stage}"
