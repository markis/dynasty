FROM python:3.12-slim-bookworm AS runtime
WORKDIR /src

RUN --mount=type=cache,target=/var/lib/apt/lists/* \
  apt-get update && apt-get install -y --no-install-recommends \
  git postgresql-client-15

ENV \
  UV_FROZEN=true \
  UV_NO_EDITABLE=true \
  UV_NO_MANAGED_PYTHON=true \
  UV_COMPILE_BYTECODE=true \
  UV_SYSTEM_PYTHON=true \
  UV_CACHE_DIR=/var/cache/uv \
  UV_PROJECT_ENVIRONMENT=/usr/local \
  HATCH_BUILD_HOOK_ENABLE_MYPYC=1

COPY uv.lock pyproject.toml ./
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
  --mount=type=cache,target=/var/cache/uv/ \
  uv sync --no-install-project

COPY . .
