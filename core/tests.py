import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch, Mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from .models import TemplateBuildJob, TemplateDefinition
from .packer_profiles import (
    BUILD_PROFILE_UBUNTU_AUTOINSTALL,
    BUILD_PROFILE_WINDOWS_UNATTEND,
    WINDOWS_FIRMWARE_BIOS_LEGACY,
    WINDOWS_FIRMWARE_UEFI_TPM,
)
from .template_builds import _render_windows_script, _render_windows_unattend, run_build_job
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


class TemplateCreateApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="builder", password="pass12345")
        self.client.force_login(self.user)

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

    @patch("core.views._inspect_url")
    def test_create_template_vmid_collision_returns_409(self, inspect_mock):
        inspect_mock.return_value = _iso_info("https://example.com/ubuntu.iso")
        TemplateDefinition.objects.create(
            owner=self.user,
            template_name="existing-template",
            template_vmid=f"100{self.user.id}",
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

        self.assertEqual(response.status_code, 409)
        self.assertIn("collision", response.json()["error"].lower())

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

    def test_status_hidden_from_other_users(self):
        self.client.force_login(self.other)
        response = self.client.get(f"/api/template/builds/{self.job.uuid}/status/")
        self.assertEqual(response.status_code, 404)


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


class DatabaseSettingsTests(TestCase):
    def test_defaults_to_sqlite_when_database_url_missing(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False):
            config = _database_settings(Path("project-root"))

        self.assertEqual(config["ENGINE"], "django.db.backends.sqlite3")
        self.assertTrue(str(config["NAME"]).endswith("project-root\\db.sqlite3"))

    def test_parses_postgres_database_url(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://capstone:secret@db:5432/capstone"},
            clear=False,
        ):
            config = _database_settings(Path("project-root"))

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "capstone")
        self.assertEqual(config["USER"], "capstone")
        self.assertEqual(config["PASSWORD"], "secret")
        self.assertEqual(config["HOST"], "db")
        self.assertEqual(config["PORT"], "5432")


@override_settings(TEMPLATE_BUILD_WORKDIR=Path("database") / "test-worker-jobs")
class WorkerExecutionTests(TestCase):
    def setUp(self):
        self.workdir = Path("database") / "test-worker-jobs"
        self.workdir.mkdir(parents=True, exist_ok=True)
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
    @patch("core.template_builds._run_command")
    def test_worker_marks_success_and_collects_software_results(self, run_command_mock, preflight_mock):
        preflight_mock.return_value = [{"check": "packer_bin", "ok": True, "value": "packer"}]

        def fake_run_command(cmd, cwd, timeout_sec, log_fp, on_output):
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
        self.assertTrue(any(item["kind"] == "user_data" for item in result.result_payload["generated_artifacts"]))

    @patch("core.template_builds._run_preflight")
    @patch("core.template_builds._run_command")
    def test_worker_marks_failure_when_command_raises(self, run_command_mock, preflight_mock):
        preflight_mock.return_value = [{"check": "packer_bin", "ok": True, "value": "packer"}]
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
