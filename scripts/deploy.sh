#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

PACKER_JOBS_HOST_PATH="${PACKER_JOBS_HOST_PATH:-/srv/capstone/packer-jobs}"
PACKER_CACHE_HOST_PATH="${PACKER_CACHE_HOST_PATH:-/srv/capstone/packer-cache}"
PACKER_NAS_HOST_PATH="${PACKER_NAS_HOST_PATH:-/mnt/capstone-nas}"

mkdir -p "${PACKER_JOBS_HOST_PATH}" "${PACKER_CACHE_HOST_PATH}"
if [ ! -d "${PACKER_NAS_HOST_PATH}" ]; then
  echo "NAS mount path does not exist: ${PACKER_NAS_HOST_PATH}" >&2
  exit 1
fi

git fetch --all
git pull --ff-only
docker compose build migrate web packer-worker
docker compose up -d db
docker compose run --rm migrate
docker compose up -d web packer-worker
docker compose ps
docker compose logs --tail=100 packer-worker
