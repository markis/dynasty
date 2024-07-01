FROM python:3.12-slim AS runtime
CMD ["-m", "dynasty.import"]
WORKDIR /src
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_DISABLE_ROOT_WARNING=1 \
  PIP_ROOT_USER_ACTION=ignore \
  PIP_CACHE_DIR="/var/cache/pip/" \
  HATCH_BUILD_HOOK_ENABLE_MYPYC=1

RUN --mount=type=cache,target=/var/lib/apt/lists/* \
  apt-get update && apt-get install -y --no-install-recommends \
  git postgresql-client-15

COPY requirements.txt /src/
RUN --mount=type=cache,target=/var/cache/pip/ \
  --mount=type=bind,src=.git,dst=/src/.git \
  pip install -r requirements.txt

COPY . .
RUN --mount=type=cache,target=/var/cache/pip/ \
  --mount=type=bind,src=.git,dst=/src/.git \
  pip install /src/
