import json
import os
import shutil
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch, Mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import DirectoryProfile, TemplateBuildJob, TemplateDefinition
from .packer_profiles import (
    BUILD_PROFILE_UBUNTU_AUTOINSTALL,
    BUILD_PROFILE_WINDOWS_UNATTEND,
    WINDOWS_FIRMWARE_BIOS_LEGACY,
    WINDOWS_FIRMWARE_UEFI_TPM,
)
from .template_builds import (
    _redact_text,
    _derive_machine_readable_error_summary,
    _run_preflight,
    _render_windows_script,
    _render_windows_unattend,
    _stage_single_iso,
    enqueue_template_build,
    ensure_worker_runtime_ready,
    recover_stale_running_jobs,
    run_build_job,
)
from .auth_backends import _candidate_endpoints
from capstoneDev.settings import _database_settings


def _iso_info(url: str, filename: str = "ubuntu.iso") -> dict:
    return {
        "final_url": url,
        "filename": filename,
        "size_bytes": 123456,
        "content_type": "application/octet-stream",
        "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT",
    }


def _staged_iso(role: str = "boot_iso", filename: str = "ubuntu.iso", reused: bool = False) -> dict:
    return {
        "role": role,
        "source_url": f"https://example.com/{filename}",
        "final_url": f"https://cdn.example.com/{filename}",
        "filename": filename,
        "size_bytes": 123456,
        "content_type": "application/octet-stream",
        "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "local_path": str(Path("database") / "test-worker-nas" / "isos" / filename),
        "manifest_path": str(Path("database") / "test-worker-nas" / "isos" / f"{filename}.json"),
        "storage_pool": "ChirpNAS_ISO_Templates",
        "iso_file": f"ChirpNAS_ISO_Templates:iso/{filename}",
        "reused": reused,
        "staged_at": timezone.now().isoformat(),
    }


def _linux_create_payload() -> dict:
    return {
        "template_name": "ubuntu-lab-template",
        "build_profile": BUILD_PROFILE_UBUNTU_AUTOINSTALL,
        "target_os": "linux",
        "iso_url": "https://example.com/ubuntu.iso",
        "software_items": [],
        "hardware": {
            "cpu": 4,
            "ram_gb": 8,
            "disk_gb": 64,
        },
        "network": {
            "bridge": "vmbr0",
            "vlan": 20,
            "ipv4_mode": "dhcp",
        },
        "linux": {
            "ssh_timeout": "45m",
        },
    }


def _windows_create_payload() -> dict:
    payload = _linux_create_payload()
    payload["build_profile"] = BUILD_PROFILE_WINDOWS_UNATTEND
    payload["target_os"] = "windows"
    payload["iso_url"] = "https://example.com/windows.iso"
    payload["windows"] = {
        "admin_username": "Administrator",
        "admin_password": "Capstone123!",
        "image_selector_type": "image_name",
        "image_selector_value": "Windows 11 Pro",
        "virtio_iso_url": "https://example.com/virtio-win.iso",
        "firmware_profile": "uefi_tpm",
        "winrm_port": 5985,
        "winrm_use_ssl": False,
        "winrm_timeout": "2h",
    }
    return payload


def _directory_profile_for(user, ad_rid: int = 1536, role: str = DirectoryProfile.ROLE_FACULTY):
    return DirectoryProfile.objects.create(
        user=user,
        ad_object_sid=f"S-1-5-21-2396734983-2603881837-2963403330-{ad_rid}",
        ad_rid=ad_rid,
        display_name=user.username,
        distinguished_name=(
            "CN=User,OU=Faculty,DC=comptech,DC=local"
            if role == DirectoryProfile.ROLE_FACULTY
            else "CN=User,OU=Students,DC=comptech,DC=local"
        ),
        user_principal_name=f"{user.username}@comptech.local",
        directory_role=role,
        raw_attributes={"objectSid": [f"S-1-5-21-2396734983-2603881837-2963403330-{ad_rid}"]},
    )


@override_settings(TEMPLATE_BUILD_WORKDIR=Path("database") / "test-api-jobs")
class TemplateCreateApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.workdir = Path("database") / "test-api-jobs"
        self.workdir.mkdir(parents=True, exist_ok=True)
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="builder", password="pass12345")
        _directory_profile_for(self.user, ad_rid=1536, role=DirectoryProfile.ROLE_FACULTY)
        self.client.force_login(self.user)

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    @patch("core.views._inspect_url")
    def test_create_template_queues_job(self, inspect_mock):
        inspect_mock.return_value = _iso_info("https://example.com/ubuntu.iso")

        response = self.client.post(
            "/api/template/create/",
            data=json.dumps(_linux_create_payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIn("job", body)
        self.assertEqual(TemplateDefinition.objects.count(), 1)
        self.assertEqual(TemplateBuildJob.objects.count(), 1)
        job = TemplateBuildJob.objects.first()
        self.assertEqual(job.status, TemplateBuildJob.STATUS_QUEUED)
        self.assertEqual(str(job.uuid), body["job"]["id"])
        self.assertEqual(body["template"]["vmid"], "1536001")
        request_manifest = self.workdir / f"job-{job.uuid}" / "request.json"
        status_manifest = self.workdir / f"job-{job.uuid}" / "status.json"
        self.assertTrue(request_manifest.exists())
        self.assertTrue(status_manifest.exists())

    @patch("core.views._inspect_url")
    def test_create_template_request_manifest_redacts_windows_password(self, inspect_mock):
        inspect_mock.return_value = _iso_info("https://example.com/windows.iso", "windows.iso")

        response = self.client.post(
            "/api/template/create/",
            data=json.dumps(_windows_create_payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job"]["id"]
        request_manifest = self.workdir / f"job-{job_id}" / "request.json"
        payload = json.loads(request_manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["request"]["windows"]["admin_password"], "[REDACTED]")

    @patch("core.views._inspect_url")
    def test_create_template_uses_next_sequential_vmid_for_same_user(self, inspect_mock):
        inspect_mock.return_value = _iso_info("https://example.com/ubuntu.iso")
        TemplateDefinition.objects.create(
            owner=self.user,
            template_name="existing-template",
            template_vmid="1536001",
            build_profile=BUILD_PROFILE_UBUNTU_AUTOINSTALL,
            target_os=TemplateDefinition.TARGET_OS_LINUX,
            iso_url="https://example.com/existing.iso",
            normalized_payload={},
            hardware={},
            network={},
        )

        response = self.client.post(
            "/api/template/create/",
            data=json.dumps(_linux_create_payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["template"]["vmid"], "1536002")

    @patch("core.views._inspect_url")
    def test_missing_directory_profile_requires_relogin(self, inspect_mock):
        inspect_mock.return_value = _iso_info("https://example.com/ubuntu.iso")
        DirectoryProfile.objects.filter(user=self.user).delete()

        response = self.client.post(
            "/api/template/create/",
            data=json.dumps(_linux_create_payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("sign out and sign back in", response.json()["error"].lower())

    @patch("core.views._inspect_url")
    def test_windows_payload_requires_windows_fields(self, inspect_mock):
        inspect_mock.return_value = _iso_info("https://example.com/windows.iso", "windows.iso")
        payload = _windows_create_payload()
        payload["windows"] = {}

        response = self.client.post(
            "/api/template/create/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertIn("Windows options are invalid.", body["error"])
        self.assertTrue(len(body.get("errors", [])) >= 1)

    @patch("core.views._inspect_url")
    def test_static_networking_is_rejected_for_templates(self, inspect_mock):
        inspect_mock.return_value = _iso_info("https://example.com/ubuntu.iso")
        payload = _linux_create_payload()
        payload["network"]["ipv4_mode"] = "static"
        payload["network"]["static_ip"] = "10.0.20.50/24"

        response = self.client.post(
            "/api/template/create/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("DHCP-ready", response.json()["error"])

    @override_settings(TEMPLATE_CREATION_POLICY="faculty_only")
    @patch("core.views._inspect_url")
    def test_student_cannot_create_template_when_policy_is_faculty_only(self, inspect_mock):
        inspect_mock.return_value = _iso_info("https://example.com/ubuntu.iso")
        student = get_user_model().objects.create_user(username="student-builder", password="pass12345")
        _directory_profile_for(student, ad_rid=1801, role=DirectoryProfile.ROLE_STUDENT)
        self.client.force_login(student)

        response = self.client.post(
            "/api/template/create/",
            data=json.dumps(_linux_create_payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Only faculty can create templates.")


class TemplateStatusApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", password="pass12345")
        self.other = user_model.objects.create_user(username="other", password="pass12345")

        self.template = TemplateDefinition.objects.create(
            owner=self.owner,
            template_name="owner-template",
            template_vmid=f"100{self.owner.id}",
            build_profile=BUILD_PROFILE_UBUNTU_AUTOINSTALL,
            target_os=TemplateDefinition.TARGET_OS_LINUX,
            iso_url="https://example.com/ubuntu.iso",
            normalized_payload={},
            hardware={},
            network={},
        )
        self.job = TemplateBuildJob.objects.create(
            owner=self.owner,
            template_definition=self.template,
            payload_snapshot={},
        )

    def test_status_visible_to_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/api/template/builds/{self.job.uuid}/status/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["job"]["template"]["build_profile"], BUILD_PROFILE_UBUNTU_AUTOINSTALL)
        self.assertNotIn("workspace", response.json()["job"]["result"])
        self.assertNotIn("log_path", response.json()["job"]["result"])

    def test_status_hidden_from_other_users(self):
        self.client.force_login(self.other)
        response = self.client.get(f"/api/template/builds/{self.job.uuid}/status/")
        self.assertEqual(response.status_code, 404)


class LoginRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="redirect-user", password="pass12345")

    def test_anonymous_home_redirects_to_login_with_next(self):
        response = self.client.get("/", follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/?next=/", response["Location"])

    def test_authenticated_login_json_returns_next_target(self):
        response = self.client.post(
            "/login/?next=/settings/",
            data=json.dumps(
                {
                    "username": "redirect-user",
                    "password": "pass12345",
                    "next": "/settings/",
                }
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="fetch",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["redirect"], "/settings/")

    def test_authenticated_get_login_redirects_to_next_target(self):
        self.client.force_login(self.user)

        response = self.client.get("/login/?next=/settings/", follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/settings/")

    def test_logout_clears_session_and_redirects_to_login(self):
        self.client.force_login(self.user)

        response = self.client.post("/logout/", follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login/")
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/?next=/", response["Location"])


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class SettingsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="settings-user",
            password="pass12345",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@comptech.local",
        )
        DirectoryProfile.objects.create(
            user=self.user,
            ad_object_sid="S-1-5-21-2396734983-2603881837-2963403330-1542",
            ad_rid=1542,
            display_name="Ada Lovelace",
            distinguished_name="CN=Ada Lovelace,OU=Faculty,DC=comptech,DC=local",
            user_principal_name="ada@comptech.local",
            department="Computer Science",
            directory_role=DirectoryProfile.ROLE_FACULTY,
            raw_attributes={},
        )

    def test_settings_page_shows_read_only_account_and_logout(self):
        self.client.force_login(self.user)

        response = self.client.get("/settings/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account")
        self.assertContains(response, "Read only")
        self.assertContains(response, "Ada Lovelace")
        self.assertContains(response, "ada@comptech.local")
        self.assertContains(response, "Computer Science")
        self.assertContains(response, "Allowed")
        self.assertContains(response, "Log out")

    def test_settings_fragment_includes_general_account_data(self):
        self.client.force_login(self.user)

        response = self.client.get("/settings/", HTTP_X_REQUESTED_WITH="fetch")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["title"], "Capstone Settings")
        self.assertIn("Ada Lovelace", body["html"])
        self.assertIn("Log out", body["html"])


class VmStartApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="vmuser", password="pass12345")

    def test_requires_login(self):
        response = self.client.post(
            "/api/vm/start/",
            data=json.dumps({"node": "Kif", "vm_id": 900}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    @patch("core.views.proxmox_services.provision_default_vm")
    def test_proxmox_failure_returns_502(self, provision_mock):
        provision_mock.side_effect = RuntimeError("boom")
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/vm/start/",
            data=json.dumps({"node": "Kif", "vm_id": 900}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()["ok"])


class ActiveDirectoryEndpointTests(TestCase):
    @patch("core.auth_backends.socket.getaddrinfo", side_effect=OSError("dns disabled"))
    def test_ip_host_adds_domain_fallback(self, _dns_mock):
        with patch.dict(
            os.environ,
            {
                "AD_LDAP_PORT": "",
                "AD_LDAP_USE_SSL": "",
            },
            clear=False,
        ):
            endpoints = _candidate_endpoints("172.27.80.64", "comptech.local")

        self.assertEqual(
            endpoints,
            [
                ("comptech.local", 389, False),
                ("172.27.80.64", 389, False),
            ],
        )

    @patch("core.auth_backends.socket.getaddrinfo", side_effect=OSError("dns disabled"))
    def test_forced_port_and_ssl_applied_to_all_hosts(self, _dns_mock):
        with patch.dict(
            os.environ,
            {
                "AD_LDAP_PORT": "636",
                "AD_LDAP_USE_SSL": "1",
            },
            clear=False,
        ):
            endpoints = _candidate_endpoints("dc1.local,dc2.local", "comptech.local")

        self.assertEqual(
            endpoints,
            [
                ("dc1.local", 636, True),
                ("dc2.local", 636, True),
            ],
        )

    @patch("core.auth_backends.socket.getaddrinfo", side_effect=OSError("dns disabled"))
    def test_explicit_ssl_false_limits_default_to_ldap(self, _dns_mock):
        with patch.dict(
            os.environ,
            {
                "AD_LDAP_PORT": "",
                "AD_LDAP_USE_SSL": "0",
            },
            clear=False,
        ):
            endpoints = _candidate_endpoints("dc1.local", "comptech.local")

        self.assertEqual(endpoints, [("dc1.local", 389, False)])

    @patch("core.auth_backends.Connection")
    @patch("core.auth_backends._candidate_endpoints")
    def test_authenticate_stops_retry_on_invalid_credentials(self, endpoints_mock, connection_mock):
        from .auth_backends import ActiveDirectoryBackend

        endpoints_mock.return_value = [
            ("dc1.local", 389, False),
            ("dc2.local", 389, False),
        ]
        conn = connection_mock.return_value
        conn.bind.return_value = False
        conn.result = {"description": "invalidCredentials"}

        with patch.dict(
            os.environ,
            {
                "AD_LDAP_HOST": "dc1.local",
                "AD_UPN_SUFFIX": "comptech.local",
            },
            clear=False,
        ):
            user = ActiveDirectoryBackend().authenticate(None, username="maxime", password="bad-pass")

        self.assertIsNone(user)
        self.assertEqual(connection_mock.call_count, 1)
        conn.unbind.assert_called_once()

    @patch("core.auth_backends.Connection")
    @patch("core.auth_backends._candidate_endpoints")
    def test_authenticate_retries_on_connectivity_failure_and_succeeds(self, endpoints_mock, connection_mock):
        from .auth_backends import ActiveDirectoryBackend

        endpoints_mock.return_value = [
            ("dc1.local", 389, False),
            ("dc2.local", 389, False),
        ]

        bad_conn = Mock()
        bad_conn.bind.side_effect = Exception("socket timeout")

        good_conn = Mock()
        good_conn.bind.return_value = True

        connection_mock.side_effect = [bad_conn, good_conn]

        with patch.dict(
            os.environ,
            {
                "AD_LDAP_HOST": "dc1.local",
                "AD_UPN_SUFFIX": "comptech.local",
            },
            clear=False,
        ):
            user = ActiveDirectoryBackend().authenticate(None, username="maxime", password="correct-pass")

        self.assertIsNotNone(user)
        self.assertEqual(user.username, "maxime")
        self.assertEqual(connection_mock.call_count, 2)
        good_conn.unbind.assert_called_once()

    @patch("core.auth_backends.Connection")
    @patch("core.auth_backends._candidate_endpoints")
    def test_authenticate_syncs_directory_profile_and_faculty_role(self, endpoints_mock, connection_mock):
        from .auth_backends import ActiveDirectoryBackend

        endpoints_mock.return_value = [("dc1.local", 389, False)]
        conn = Mock()
        conn.bind.return_value = True
        conn.entries = [Mock(entry_attributes_as_dict={
            "objectSid": ["S-1-5-21-2396734983-2603881837-2963403330-1693"],
            "displayName": ["Joel Wiredu"],
            "givenName": ["Joel"],
            "sn": ["Wiredu"],
            "distinguishedName": ["CN=Joel Wiredu,OU=Faculty,DC=comptech,DC=local"],
            "memberOf": ["CN=Domain Admins,CN=Users,DC=comptech,DC=local"],
            "userPrincipalName": ["joel.wiredu@comptech.local"],
            "department": ["Computer Technology"],
            "company": ["Ball State University"],
        })]
        connection_mock.return_value = conn

        with patch.dict(
            os.environ,
            {
                "AD_LDAP_HOST": "dc1.local",
                "AD_UPN_SUFFIX": "comptech.local",
                "AD_BASE_DN": "DC=comptech,DC=local",
            },
            clear=False,
        ):
            user = ActiveDirectoryBackend().authenticate(None, username="joel.wiredu", password="correct-pass")

        self.assertIsNotNone(user)
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertEqual(user.first_name, "Joel")
        profile = user.directory_profile
        self.assertEqual(profile.ad_rid, 1693)
        self.assertEqual(profile.directory_role, DirectoryProfile.ROLE_FACULTY)


class DatabaseSettingsTests(TestCase):
    def test_defaults_to_sqlite_when_database_url_missing(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False):
            config = _database_settings(Path("project-root"))

        self.assertEqual(config["ENGINE"], "django.db.backends.sqlite3")
        self.assertTrue(str(config["NAME"]).endswith("project-root\\db.sqlite3"))

    def test_parses_postgres_database_url(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://capstone:secret@postgres.internal:5432/capstone"},
            clear=False,
        ):
            config = _database_settings(Path("project-root"))

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "capstone")
        self.assertEqual(config["USER"], "capstone")
        self.assertEqual(config["PASSWORD"], "secret")
        self.assertEqual(config["HOST"], "postgres.internal")
        self.assertEqual(config["PORT"], "5432")


class StaticSettingsTests(TestCase):
    @override_settings(DEBUG=False)
    def test_static_root_and_manifest_storage_configured(self):
        from django.conf import settings

        self.assertTrue(str(settings.STATIC_ROOT).endswith("staticfiles"))
        self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", settings.MIDDLEWARE)
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )


@override_settings(
    TEMPLATE_BUILD_WORKDIR=Path("database") / "test-worker-jobs",
    PACKER_CACHE_DIR=Path("database") / "test-worker-cache",
    PACKER_NAS_ROOT=Path("database") / "test-worker-nas",
    PACKER_NAS_ISO_DIR=Path("database") / "test-worker-nas" / "isos",
    PACKER_NAS_ARCHIVE_DIR=Path("database") / "test-worker-nas" / "archive",
    PROXMOX_ISO_STORAGE_POOL="ChirpNAS_ISO_Templates",
)
class WorkerExecutionTests(TestCase):
    def setUp(self):
        self.workdir = Path("database") / "test-worker-jobs"
        self.cache_dir = Path("database") / "test-worker-cache"
        self.nas_root = Path("database") / "test-worker-nas"
        self.nas_iso_dir = self.nas_root / "isos"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.nas_iso_dir.mkdir(parents=True, exist_ok=True)
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="worker", password="pass12345")
        self.template = TemplateDefinition.objects.create(
            owner=self.user,
            template_name="worker-template",
            template_vmid=f"100{self.user.id}",
            build_profile=BUILD_PROFILE_UBUNTU_AUTOINSTALL,
            target_os=TemplateDefinition.TARGET_OS_LINUX,
            iso_url="https://example.com/ubuntu.iso",
            normalized_payload={},
            hardware={},
            network={},
        )

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)
        shutil.rmtree(self.cache_dir, ignore_errors=True)
        shutil.rmtree(self.nas_root, ignore_errors=True)

    def _job_payload(self):
        return {
            "template_name": self.template.template_name,
            "template_vmid": self.template.template_vmid,
            "build_profile": BUILD_PROFILE_UBUNTU_AUTOINSTALL,
            "target_os": "linux",
            "iso_url": "https://example.com/ubuntu.iso",
            "software_items": [
                {
                    "id": "software-1",
                    "kind": "url",
                    "label": "Tool",
                    "url": "https://example.com/tool.sh",
                    "artifact_type": "sh",
                    "install_strategy": "script",
                    "silent_args": "",
                }
            ],
            "hardware": {"cpu": 2, "ram_gb": 4, "disk_gb": 32},
            "network": {"bridge": "vmbr0", "vlan": None, "ipv4_mode": "dhcp"},
            "linux": {"ssh_timeout": "45m"},
            "windows": {},
            "ansible": {},
            "guest_networking": "dhcp",
        }

    @patch("core.template_builds._run_preflight")
    @patch("core.template_builds._stage_required_isos")
    @patch("core.template_builds._run_command")
    def test_worker_marks_success_and_collects_software_results(self, run_command_mock, stage_mock, preflight_mock):
        preflight_mock.return_value = [{"check": "packer_bin", "ok": True, "value": "packer"}]
        stage_mock.return_value = [_staged_iso()]

        def fake_run_command(cmd, cwd, timeout_sec, log_fp, on_output, **kwargs):
            on_output("CAPSTONE_ITEM_RESULT|software-1|installed|0|Tool installed")
            return None

        run_command_mock.side_effect = fake_run_command

        job = TemplateBuildJob.objects.create(
            owner=self.user,
            template_definition=self.template,
            payload_snapshot=self._job_payload(),
            status=TemplateBuildJob.STATUS_RUNNING,
            stage=TemplateBuildJob.STAGE_INIT,
        )

        result = run_build_job(job)
        result.refresh_from_db()

        self.assertEqual(result.status, TemplateBuildJob.STATUS_SUCCEEDED)
        self.assertEqual(result.stage, TemplateBuildJob.STAGE_DONE)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.result_payload["software_results"][0]["status"], "installed")
        self.assertEqual(result.result_payload["preflight"][0]["check"], "packer_bin")
        self.assertEqual(result.result_payload["staged_isos"][0]["iso_file"], "ChirpNAS_ISO_Templates:iso/ubuntu.iso")
        self.assertTrue(any(item["kind"] == "user_data" for item in result.result_payload["generated_artifacts"]))
        self.assertTrue((self.workdir / f"job-{job.uuid}" / "status.json").exists())
        self.assertTrue((self.workdir / f"job-{job.uuid}" / "results" / "result.json").exists())
        self.assertTrue((self.workdir / f"job-{job.uuid}" / "results" / "iso-stage.json").exists())
        vars_payload = json.loads((self.workdir / f"job-{job.uuid}" / "generated" / "template.auto.pkrvars.json").read_text(encoding="utf-8"))
        self.assertEqual(vars_payload["iso_file"], "ChirpNAS_ISO_Templates:iso/ubuntu.iso")
        self.assertNotIn("iso_url", vars_payload)
        self.assertTrue(result.result_payload["log_available"])

    @patch("core.template_builds._run_preflight")
    @patch("core.template_builds._stage_required_isos")
    @patch("core.template_builds._run_command")
    def test_worker_marks_failure_when_command_raises(self, run_command_mock, stage_mock, preflight_mock):
        preflight_mock.return_value = [{"check": "packer_bin", "ok": True, "value": "packer"}]
        stage_mock.return_value = [_staged_iso()]
        run_command_mock.side_effect = RuntimeError("packer failed")

        job = TemplateBuildJob.objects.create(
            owner=self.user,
            template_definition=self.template,
            payload_snapshot=self._job_payload(),
            status=TemplateBuildJob.STATUS_RUNNING,
            stage=TemplateBuildJob.STAGE_INIT,
        )

        result = run_build_job(job)
        result.refresh_from_db()

        self.assertEqual(result.status, TemplateBuildJob.STATUS_FAILED)
        self.assertEqual(result.stage, TemplateBuildJob.STAGE_DONE)
        self.assertIn("packer failed", result.error_summary)
        self.assertTrue((self.workdir / f"job-{job.uuid}" / "results" / "error-summary.txt").exists())

    def test_enqueue_template_build_writes_request_and_status_manifests(self):
        payload = self._job_payload()
        payload["windows"] = {"admin_password": "Capstone123!"}

        job = enqueue_template_build(self.template, payload)

        workspace = self.workdir / f"job-{job.uuid}"
        request_manifest = json.loads((workspace / "request.json").read_text(encoding="utf-8"))
        status_manifest = json.loads((workspace / "status.json").read_text(encoding="utf-8"))

        self.assertEqual(request_manifest["request"]["windows"]["admin_password"], "[REDACTED]")
        self.assertEqual(status_manifest["job"]["status"], TemplateBuildJob.STATUS_QUEUED)

    def test_recover_stale_running_jobs_marks_job_failed(self):
        stale_time = timezone.now() - timedelta(seconds=3600)
        job = TemplateBuildJob.objects.create(
            owner=self.user,
            template_definition=self.template,
            payload_snapshot=self._job_payload(),
            status=TemplateBuildJob.STATUS_RUNNING,
            stage=TemplateBuildJob.STAGE_BUILD,
            started_at=stale_time,
            last_heartbeat_at=stale_time,
        )

        recovered = recover_stale_running_jobs()
        job.refresh_from_db()

        self.assertEqual(recovered, 1)
        self.assertEqual(job.status, TemplateBuildJob.STATUS_FAILED)
        self.assertEqual(job.error_summary, "worker_restart_or_stale_claim")

    @override_settings(TEMPLATE_BUILD_DEV_BYPASS=True, PACKER_BIN="missing-packer", PACKER_ISO_TOOL="missing-tool")
    def test_worker_runtime_ready_skips_prereqs_in_dev_bypass(self):
        checks = ensure_worker_runtime_ready()

        self.assertEqual(len(checks), 2)
        self.assertTrue(all(check.get("skipped") for check in checks))
        self.assertEqual(checks[0]["reason"], "dev_bypass")

    @override_settings(TEMPLATE_BUILD_DEV_BYPASS=False, PACKER_BIN="missing-packer")
    def test_worker_runtime_ready_requires_packer_when_bypass_disabled(self):
        with self.assertRaises(RuntimeError):
            ensure_worker_runtime_ready()

    @override_settings(TEMPLATE_BUILD_DEV_BYPASS=True, PACKER_BIN="missing-packer", PACKER_ISO_TOOL="missing-tool")
    def test_run_build_job_completes_in_dev_bypass_mode(self):
        job = TemplateBuildJob.objects.create(
            owner=self.user,
            template_definition=self.template,
            payload_snapshot=self._job_payload(),
            status=TemplateBuildJob.STATUS_RUNNING,
            stage=TemplateBuildJob.STAGE_PREFLIGHT,
            started_at=timezone.now(),
        )

        result = run_build_job(job)
        result.refresh_from_db()

        workspace = self.workdir / f"job-{job.uuid}"
        self.assertEqual(result.status, TemplateBuildJob.STATUS_SUCCEEDED)
        self.assertEqual(result.stage, TemplateBuildJob.STAGE_DONE)
        self.assertEqual(result.exit_code, 0)
        self.assertIsNotNone(result.started_at)
        self.assertIsNotNone(result.finished_at)
        self.assertIsNotNone(result.last_heartbeat_at)
        self.assertTrue(result.result_payload["dev_bypass"])
        self.assertEqual(result.result_payload["execution_mode"], "dev_bypass")
        self.assertIn("Dev mode execution", result.result_payload["summary"])
        self.assertTrue((workspace / "logs" / "packer.log").exists())
        self.assertTrue((workspace / "results" / "result.json").exists())
        self.assertTrue((workspace / "results" / "preflight.json").exists())
        self.assertTrue((workspace / "results" / "software-results.json").exists())

        preflight_payload = json.loads((workspace / "results" / "preflight.json").read_text(encoding="utf-8"))
        self.assertTrue(preflight_payload["checks"][0]["skipped"])
        self.assertEqual(preflight_payload["checks"][0]["reason"], "dev_bypass")


@override_settings(
    PACKER_NAS_ROOT=Path("database") / "test-stage-nas",
    PACKER_NAS_ISO_DIR=Path("database") / "test-stage-nas" / "isos",
    PROXMOX_ISO_STORAGE_POOL="ChirpNAS_ISO_Templates",
    PROXMOX_STORAGE_POOL="local-lvm",
    PROXMOX_NODE="pve",
)
class IsoStagingTests(TestCase):
    def setUp(self):
        self.nas_root = Path("database") / "test-stage-nas"
        self.iso_dir = self.nas_root / "isos"
        self.iso_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.nas_root / "stage.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.nas_root, ignore_errors=True)

    def test_stage_single_iso_downloads_and_writes_manifest(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.url = "https://cdn.example.com/ubuntu.iso"
        response.headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": "11",
            "Last-Modified": "Tue, 02 Apr 2024 00:00:00 GMT",
        }
        response.iter_content = Mock(return_value=[b"hello ", b"world"])
        response.raise_for_status = Mock()

        with self.log_path.open("a", encoding="utf-8") as log_fp, patch("core.template_builds.requests.get", return_value=response):
            staged = _stage_single_iso(
                role="boot_iso",
                source_url="https://example.com/ubuntu.iso",
                preferred_filename="ubuntu.iso",
                log_fp=log_fp,
            )

        self.assertFalse(staged["reused"])
        self.assertEqual(staged["iso_file"], "ChirpNAS_ISO_Templates:iso/ubuntu.iso")
        self.assertTrue((self.iso_dir / "ubuntu.iso").exists())
        self.assertTrue((self.iso_dir / "ubuntu.iso.json").exists())

    def test_stage_single_iso_reuses_existing_manifest(self):
        iso_path = self.iso_dir / "ubuntu.iso"
        iso_path.write_bytes(b"cached")
        manifest_path = self.iso_dir / "ubuntu.iso.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "source_url": "https://example.com/ubuntu.iso",
                    "final_url": "https://cdn.example.com/ubuntu.iso",
                    "filename": "ubuntu.iso",
                }
            ),
            encoding="utf-8",
        )

        with self.log_path.open("a", encoding="utf-8") as log_fp, patch("core.template_builds.requests.get") as get_mock:
            staged = _stage_single_iso(
                role="boot_iso",
                source_url="https://example.com/ubuntu.iso",
                preferred_filename="ubuntu.iso",
                log_fp=log_fp,
            )

        self.assertTrue(staged["reused"])
        self.assertEqual(staged["local_path"], str(iso_path))
        get_mock.assert_not_called()

    def test_stage_single_iso_conflicting_filename_uses_suffix(self):
        (self.iso_dir / "ubuntu.iso").write_bytes(b"existing")
        (self.iso_dir / "ubuntu.iso.json").write_text(
            json.dumps({"source_url": "https://other.example.com/ubuntu.iso"}),
            encoding="utf-8",
        )

        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.url = "https://cdn.example.com/ubuntu.iso"
        response.headers = {"Content-Length": "4"}
        response.iter_content = Mock(return_value=[b"test"])
        response.raise_for_status = Mock()

        with self.log_path.open("a", encoding="utf-8") as log_fp, patch("core.template_builds.requests.get", return_value=response):
            staged = _stage_single_iso(
                role="boot_iso",
                source_url="https://example.com/ubuntu.iso",
                preferred_filename="ubuntu.iso",
                log_fp=log_fp,
            )

        self.assertEqual(staged["filename"], "ubuntu-2.iso")
        self.assertTrue((self.iso_dir / "ubuntu-2.iso").exists())

    @patch("core.template_builds._fetch_proxmox_storage")
    def test_run_preflight_requires_distinct_iso_storage_pool(self, fetch_storage_mock):
        fetch_storage_mock.return_value = {"storage": "local-lvm", "content": "iso,images", "type": "dir"}
        with override_settings(PROXMOX_STORAGE_POOL="same-pool", PROXMOX_ISO_STORAGE_POOL="same-pool"):
            with self.log_path.open("a", encoding="utf-8") as log_fp:
                with self.assertRaises(RuntimeError):
                    _run_preflight(BUILD_PROFILE_UBUNTU_AUTOINSTALL, _linux_create_payload(), log_fp)

    @patch("core.template_builds._fetch_proxmox_storage")
    def test_run_preflight_accepts_iso_capable_storage(self, fetch_storage_mock):
        fetch_storage_mock.return_value = {
            "storage": "ChirpNAS_ISO_Templates",
            "content": "iso,images",
            "type": "dir",
        }
        with override_settings(PACKER_BIN="packer"):
            with self.log_path.open("a", encoding="utf-8") as log_fp, patch("core.template_builds._detect_iso_tool", return_value="xorriso"), patch("core.template_builds.shutil.which", return_value="/usr/bin/packer"):
                results = _run_preflight(BUILD_PROFILE_UBUNTU_AUTOINSTALL, _linux_create_payload(), log_fp)

        self.assertTrue(any(item["check"] == "iso_storage_pool" for item in results))


class ArtifactGenerationTests(TestCase):
    def test_windows_unattend_uses_bios_disk_layout(self):
        unattend = _render_windows_unattend(
            {
                "windows": {
                    "admin_username": "Administrator",
                    "admin_password": "Capstone123!",
                    "image_selector_type": "image_name",
                    "image_selector_value": "Windows Server 2022 SERVERSTANDARD",
                    "firmware_profile": WINDOWS_FIRMWARE_BIOS_LEGACY,
                }
            }
        )

        self.assertIn("<WillWipeDisk>true</WillWipeDisk>", unattend)
        self.assertIn("<PartitionID>2</PartitionID>", unattend)
        self.assertIn("winrm quickconfig -q;", unattend)
        self.assertIn("sc.exe config winrm start= auto;", unattend)

    def test_windows_unattend_uses_uefi_disk_layout(self):
        unattend = _render_windows_unattend(
            {
                "windows": {
                    "admin_username": "Administrator",
                    "admin_password": "Capstone123!",
                    "image_selector_type": "image_index",
                    "image_selector_value": "6",
                    "firmware_profile": WINDOWS_FIRMWARE_UEFI_TPM,
                }
            }
        )

        self.assertIn("<Type>EFI</Type>", unattend)
        self.assertIn("<Type>MSR</Type>", unattend)
        self.assertIn("<PartitionID>3</PartitionID>", unattend)
        self.assertIn("<Key>/IMAGE/INDEX</Key>", unattend)

    def test_windows_bootstrap_installs_guest_agent_and_syspreps(self):
        script = _render_windows_script([])

        self.assertIn("Find-VirtioGuestAgentInstaller", script)
        self.assertIn("msiexec.exe", script)
        self.assertIn("CAPSTONE_STAGE|sealing", script)
        self.assertIn("Sysprep.exe", script)

    def test_windows_uefi_hcl_uses_efi_type(self):
        hcl = (Path("core") / "packer" / "templates" / "windows_unattend_uefi.pkr.hcl").read_text(encoding="utf-8")

        self.assertIn("efi_type = \"4m\"", hcl)
        self.assertNotIn("\n    type = \"4m\"\n", hcl)

    def test_ubuntu_cloud_init_cd_uses_iso_storage_pool(self):
        hcl = (Path("core") / "packer" / "templates" / "ubuntu_autoinstall.pkr.hcl").read_text(encoding="utf-8")

        self.assertIn("cd_label         = \"cidata\"", hcl)
        self.assertIn("iso_file = var.iso_file", hcl)
        self.assertIn("iso_storage_pool = var.iso_storage_pool", hcl)
        self.assertNotIn("iso_download_pve = true", hcl)

    def test_windows_autounattend_cd_uses_iso_storage_pool(self):
        bios_hcl = (Path("core") / "packer" / "templates" / "windows_unattend_bios.pkr.hcl").read_text(encoding="utf-8")
        uefi_hcl = (Path("core") / "packer" / "templates" / "windows_unattend_uefi.pkr.hcl").read_text(encoding="utf-8")

        self.assertIn("iso_file = var.iso_file", bios_hcl)
        self.assertIn("cd_label         = \"AUTOUNATTEND\"", bios_hcl)
        self.assertIn("iso_storage_pool = var.iso_storage_pool", bios_hcl)
        self.assertIn("iso_file = var.iso_file", uefi_hcl)
        self.assertIn("cd_label         = \"AUTOUNATTEND\"", uefi_hcl)
        self.assertIn("iso_storage_pool = var.iso_storage_pool", uefi_hcl)

    def test_boot_and_windows_driver_isos_use_staged_proxmox_iso_files(self):
        ubuntu_hcl = (Path("core") / "packer" / "templates" / "ubuntu_autoinstall.pkr.hcl").read_text(encoding="utf-8")
        debian_hcl = (Path("core") / "packer" / "templates" / "debian_preseed.pkr.hcl").read_text(encoding="utf-8")
        bios_hcl = (Path("core") / "packer" / "templates" / "windows_unattend_bios.pkr.hcl").read_text(encoding="utf-8")
        uefi_hcl = (Path("core") / "packer" / "templates" / "windows_unattend_uefi.pkr.hcl").read_text(encoding="utf-8")

        self.assertIn("iso_file = var.iso_file", ubuntu_hcl)
        self.assertIn("iso_file = var.iso_file", debian_hcl)
        self.assertIn("iso_file = var.windows_virtio_iso_file", bios_hcl)
        self.assertIn("iso_file = var.windows_virtio_iso_file", uefi_hcl)

    def test_log_redaction_masks_secret_values(self):
        redacted = _redact_text("token=secret-value password=abc123", ["secret-value", "abc123"])

        self.assertNotIn("secret-value", redacted)
        self.assertNotIn("abc123", redacted)

    def test_machine_readable_error_summary_prefers_specific_error_event(self):
        summary = _derive_machine_readable_error_summary(
            "Command failed (1): /usr/bin/packer build",
            [
                {"type": "ui", "data": ["say", "\\n==> Wait completed after 1 minute 37 seconds"]},
                {"type": "error", "data": ["501 for data too large"]},
            ],
        )

        self.assertEqual(summary, "501 for data too large")

    def test_machine_readable_error_summary_falls_back_when_no_error_event_exists(self):
        summary = _derive_machine_readable_error_summary(
            "Command failed (1): /usr/bin/packer build",
            [
                {"type": "ui", "data": ["say", "\\n==> Build starting"]},
            ],
        )

        self.assertEqual(summary, "Command failed (1): /usr/bin/packer build")
