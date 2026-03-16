#!/bin/sh
set -eu

: "${TEMPLATE_BUILD_WORKDIR:=/var/lib/capstone/jobs}"
: "${PACKER_CACHE_DIR:=/var/lib/capstone/packer-cache}"
: "${PACKER_NAS_ROOT:=/mnt/capstone-nas}"
: "${PACKER_NAS_ARCHIVE_DIR:=${PACKER_NAS_ROOT}/archive}"

mkdir -p "${TEMPLATE_BUILD_WORKDIR}" "${PACKER_CACHE_DIR}"
if [ -d "${PACKER_NAS_ROOT}" ]; then
    mkdir -p "${PACKER_NAS_ARCHIVE_DIR}" || true
fi

if ! command -v packer >/dev/null 2>&1; then
    echo "packer binary not found in worker image" >&2
    exit 1
fi

packer version >/dev/null
exec python manage.py run_template_build_worker
