# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────────────────────
# The judge worker: nsjail plus the toolchains it runs submissions with.
#   docker build -f infra/docker/judge.Dockerfile -t codejudge-judge apps/api
# Runs unprivileged: compose and the ECS task drop every capability and apply
# infra/docker/judge-seccomp.json (docs/architecture/sandbox.md).
# ─────────────────────────────────────────────────────────────────────────────
ARG DEBIAN_IMAGE=debian:trixie-slim
ARG NSJAIL_VERSION=3.6
# Optional Debian mirror for slow routes to deb.debian.org: an http URL ending in /debian
# that also serves <url>-security (e.g. http://ftp.de.debian.org/debian). Empty keeps the
# default.
ARG APT_MIRROR=

FROM ghcr.io/astral-sh/uv:0.9.17 AS uv

# ── nsjail, built from a pinned release tag ───────────────────────────────────
FROM ${DEBIAN_IMAGE} AS nsjail
ARG NSJAIL_VERSION
ARG APT_MIRROR
RUN if [ -n "${APT_MIRROR}" ]; then \
      sed -i -e "s#^URIs: http://deb.debian.org/debian\$#URIs: ${APT_MIRROR}#" \
             -e "s#^URIs: http://deb.debian.org/debian-security\$#URIs: ${APT_MIRROR}-security#" \
             /etc/apt/sources.list.d/debian.sources; fi
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git make g++ pkg-config bison flex protobuf-compiler \
      libprotobuf-dev libnl-route-3-dev \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "${NSJAIL_VERSION}" https://github.com/google/nsjail.git /src \
 && make -C /src -j"$(nproc)" \
 && install -m 0755 /src/nsjail /nsjail

# ── Toolchains (the same ones submissions use) ────────────────────────────────
FROM ${DEBIAN_IMAGE} AS toolchains
ARG APT_MIRROR
RUN if [ -n "${APT_MIRROR}" ]; then \
      sed -i -e "s#^URIs: http://deb.debian.org/debian\$#URIs: ${APT_MIRROR}#" \
             -e "s#^URIs: http://deb.debian.org/debian-security\$#URIs: ${APT_MIRROR}-security#" \
             /etc/apt/sources.list.d/debian.sources; fi
RUN apt-get update && apt-get install -y --no-install-recommends \
      tini ca-certificates libprotobuf32t64 libnl-route-3-200 \
      python3 python3-venv g++ openjdk-21-jdk-headless nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && ln -s "/usr/lib/jvm/java-21-openjdk-$(dpkg --print-architecture)" /usr/lib/jvm/java-21

# ── The worker's own virtualenv, built on the same system Python ─────────────
FROM toolchains AS build
COPY --from=uv /uv /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/bin/python3 UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project
COPY pyproject.toml uv.lock README.md ./
COPY src src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM toolchains AS judge
COPY --from=nsjail /nsjail /usr/local/bin/nsjail
COPY --from=build /opt/venv /opt/venv
# The worker lives in /opt, which the sandbox never mounts: submissions see /usr, /lib
# and /bin read-only, their own box and a private /tmp, nothing of the worker.
ENV PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 TZ=UTC
RUN groupadd --system --gid 10001 judge \
 && useradd --system --uid 10001 --gid judge --home-dir /var/cache/codejudge \
      --no-create-home --shell /usr/sbin/nologin judge \
 && install -d -o judge -g judge /var/cache/codejudge
USER 10001:10001
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["codejudge", "judge"]

# ── Test target: the same image plus pytest (make test-judge mounts the tests) ─
FROM build AS build-test
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-editable

FROM judge AS judge-test
COPY --from=build-test /opt/venv /opt/venv
WORKDIR /src
CMD ["pytest", "-q", "tests/judge"]
