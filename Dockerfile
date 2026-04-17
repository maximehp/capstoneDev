FROM python:3.12-slim AS app-base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

COPY . /app/

ENTRYPOINT ["docker-entrypoint.sh"]

FROM app-base AS web-runtime

EXPOSE 8000
CMD ["gunicorn", "capstoneDev.wsgi:application", "--bind", "0.0.0.0:8000"]

FROM app-base AS packer-runtime

ENV HOME=/tmp/capstone-worker
ENV XDG_CONFIG_HOME=/tmp/capstone-worker/.config
ENV PACKER_PLUGIN_PATH=/tmp/capstone-worker/.config/packer/plugins
ENV TMPDIR=/tmp/capstone-worker/tmp

ARG PACKER_VERSION=1.11.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl jq unzip xorriso \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "${arch}" in \
        amd64) packer_arch="amd64" ;; \
        arm64) packer_arch="arm64" ;; \
        *) echo "unsupported packer architecture: ${arch}" >&2; exit 1 ;; \
    esac; \
    curl -fL --retry 5 --retry-delay 2 --retry-all-errors \
        -o /tmp/packer.zip \
        "https://releases.hashicorp.com/packer/${PACKER_VERSION}/packer_${PACKER_VERSION}_linux_${packer_arch}.zip"; \
    unzip /tmp/packer.zip -d /usr/bin; \
    chmod +x /usr/bin/packer; \
    rm -f /tmp/packer.zip; \
    /usr/bin/packer version

COPY docker/packer-worker/start.sh /usr/local/bin/packer-worker-start.sh
RUN chmod +x /usr/local/bin/packer-worker-start.sh

CMD ["/usr/local/bin/packer-worker-start.sh"]
