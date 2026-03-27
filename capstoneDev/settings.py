"""
Django settings for capstoneDev project.
"""

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_str(name: str, default: str = "", aliases: tuple[str, ...] = ()) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    for alias in aliases:
        alias_value = os.environ.get(alias, "").strip()
        if alias_value:
            return alias_value
    return default


def _env_bool(name: str, default: bool = False, aliases: tuple[str, ...] = ()) -> bool:
    raw = _env_str(name, "", aliases=aliases)
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _database_settings(base_dir: Path) -> dict:
    database_url = _env_str("DATABASE_URL", default="")
    if not database_url:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(base_dir / "db.sqlite3"),
        }

    parsed = urlparse(database_url)
    scheme = (parsed.scheme or "").lower()
    running_tests = "test" in sys.argv[1:]
    in_container = Path("/.dockerenv").exists()

    if running_tests and not in_container and (parsed.hostname or "").strip().lower() == "db":
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(base_dir / "db.sqlite3"),
        }

    if scheme in {"postgres", "postgresql"}:
        db_name = unquote((parsed.path or "").lstrip("/"))
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": db_name,
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or 5432),
        }

    if scheme == "sqlite":
        if parsed.netloc and parsed.path:
            db_name = f"//{parsed.netloc}{unquote(parsed.path)}"
        else:
            db_name = unquote(parsed.path or "") or str(base_dir / "db.sqlite3")
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": db_name,
        }

    raise RuntimeError(f"Unsupported DATABASE_URL scheme: {scheme or 'unknown'}")


SECRET_KEY = _env_str("SECRET_KEY", default=_env_str("DJANGO_SECRET_KEY", default="secret"))
DEBUG = _env_bool("DEBUG", default=_env_bool("DJANGO_DEBUG", default=True))
ALLOWED_HOSTS = [
    host.strip() for host in _env_str("DJANGO_ALLOWED_HOSTS", default="127.0.0.1,localhost").split(",") if host.strip()
]

if not DEBUG:
    missing = []
    for key in [
        "SECRET_KEY",
        "PROXMOX_BASE_URL",
        "PROXMOX_TOKEN_ID",
        "PROXMOX_TOKEN_SECRET",
        "AD_LDAP_HOST",
        "AD_UPN_SUFFIX",
        "AD_BASE_DN",
    ]:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    if SECRET_KEY == "secret":
        raise RuntimeError("SECRET_KEY must be set to a non-default value when DEBUG is false")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "capstoneDev.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "capstoneDev.wsgi.application"

DATABASES = {"default": _database_settings(BASE_DIR)}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

AUTHENTICATION_BACKENDS = [
    "core.auth_backends.ActiveDirectoryBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Template/Packer runtime settings
TEMPLATE_CREATION_POLICY = _env_str("TEMPLATE_CREATION_POLICY", default="allow_all").lower()
if TEMPLATE_CREATION_POLICY not in {"allow_all", "faculty_only"}:
    TEMPLATE_CREATION_POLICY = "allow_all"

TEMPLATE_BUILD_WORKDIR = Path(
    _env_str("TEMPLATE_BUILD_WORKDIR", default=str(BASE_DIR / "database" / "packer_templates" / "jobs"))
)
TEMPLATE_BUILD_POLL_SECONDS = int(_env_str("TEMPLATE_BUILD_POLL_SECONDS", default="5"))
TEMPLATE_BUILD_MAX_TIMEOUT_SEC = int(_env_str("TEMPLATE_BUILD_MAX_TIMEOUT_SEC", default="10800"))
TEMPLATE_BUILD_HEARTBEAT_SECONDS = int(_env_str("TEMPLATE_BUILD_HEARTBEAT_SECONDS", default="15"))
TEMPLATE_BUILD_STALE_AFTER_SECONDS = int(_env_str("TEMPLATE_BUILD_STALE_AFTER_SECONDS", default="900"))
TEMPLATE_BUILD_CONCURRENCY = int(_env_str("TEMPLATE_BUILD_CONCURRENCY", default="1"))
TEMPLATE_BUILD_DEV_BYPASS = _env_bool("TEMPLATE_BUILD_DEV_BYPASS", default=False)
PACKER_BIN = _env_str("PACKER_BIN", default="packer")
PACKER_PROXMOX_PLUGIN_SOURCE = _env_str(
    "PACKER_PROXMOX_PLUGIN_SOURCE",
    default="github.com/hashicorp/proxmox",
)
PACKER_PROXMOX_PLUGIN_VERSION = _env_str("PACKER_PROXMOX_PLUGIN_VERSION", default=">= 1.1.0")
PACKER_ISO_TOOL = _env_str("PACKER_ISO_TOOL", default="")
PACKER_CACHE_DIR = Path(_env_str("PACKER_CACHE_DIR", default=str(BASE_DIR / "database" / "packer_templates" / "cache")))
PACKER_NAS_ROOT = Path(_env_str("PACKER_NAS_ROOT", default="/mnt/capstone-nas"))
PACKER_NAS_ISO_DIR = Path(_env_str("PACKER_NAS_ISO_DIR", default=str(PACKER_NAS_ROOT / "isos")))
PACKER_NAS_ARCHIVE_DIR = Path(
    _env_str("PACKER_NAS_ARCHIVE_DIR", default=str(PACKER_NAS_ROOT / "archive"))
)
ALLOW_PRIVATE_TEMPLATE_ASSET_URLS = _env_bool("ALLOW_PRIVATE_TEMPLATE_ASSET_URLS", default=True)

PROXMOX_NODE = _env_str("PROXMOX_NODE", default="")
PROXMOX_STORAGE_POOL = _env_str("PROXMOX_STORAGE_POOL", default="local-lvm")
PROXMOX_ISO_STORAGE_POOL = _env_str("PROXMOX_ISO_STORAGE_POOL", default=PROXMOX_STORAGE_POOL)
