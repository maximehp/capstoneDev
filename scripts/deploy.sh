#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo ".env file is required for deployment" >&2
  exit 1
fi

set -a
. ./.env
set +a

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL must be set in .env" >&2
  exit 1
fi

if printf '%s' "${DATABASE_URL}" | grep -q '@db:'; then
  echo "DATABASE_URL still points at Docker host 'db'. Use the external PostgreSQL host instead." >&2
  exit 1
fi

PACKER_JOBS_HOST_PATH="${PACKER_JOBS_HOST_PATH:-/srv/capstone/packer-jobs}"
PACKER_NAS_HOST_PATH="${PACKER_NAS_HOST_PATH:-/mnt/capstone-nas}"
PACKER_CACHE_DIR="${PACKER_CACHE_DIR:-${PACKER_NAS_HOST_PATH}/Templates/packer-cache}"
PACKER_NAS_ARCHIVE_DIR="${PACKER_NAS_ARCHIVE_DIR:-${PACKER_NAS_HOST_PATH}/Templates/archives}"
APP_USERDATA_DIR="${APP_USERDATA_DIR:-${PACKER_NAS_HOST_PATH}/UserData}"

mkdir -p "${PACKER_JOBS_HOST_PATH}"

if [ ! -d "${PACKER_NAS_HOST_PATH}" ]; then
  echo "NAS mount path does not exist: ${PACKER_NAS_HOST_PATH}" >&2
  exit 1
fi

mkdir -p "${PACKER_CACHE_DIR}" "${PACKER_NAS_ARCHIVE_DIR}" "${APP_USERDATA_DIR}"

git fetch --all
git pull --ff-only
docker compose build migrate web packer-worker
docker compose run --rm migrate
docker compose up -d web packer-worker
docker compose ps
docker compose logs --tail=100 packer-worker
