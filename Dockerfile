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

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg jq wget xorriso \
    && wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg \
    && . /etc/os-release \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/hashicorp.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends packer \
    && rm -rf /var/lib/apt/lists/*

COPY docker/packer-worker/start.sh /usr/local/bin/packer-worker-start.sh
RUN chmod +x /usr/local/bin/packer-worker-start.sh

CMD ["/usr/local/bin/packer-worker-start.sh"]
