# ==========================================
# Stage: image-base
# ==========================================
FROM python:3.12.11-slim-trixie AS image-base

RUN apt-get update && apt-get install -y \
    curl \
    xvfb \
    x11-utils \
    dbus-x11 \
    # env substitution
    gettext-base \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src" \
    PLAYWRIGHT_BROWSERS_PATH="/ms-playwright" \
    PLAYWRIGHT_HOST_PLATFORM_OVERRIDE="debian12-x64" \
    XDG_CACHE_HOME="/tmp/.cache" \
    XDG_CONFIG_HOME="/tmp/.config" \
    PROJECT_NAME="pipelines" \
    # uv: install packages into /venv
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_CACHE_DIR="/tmp/.cache/uv" \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON="/usr/local/bin/python3" \
    PATH="/venv/bin:/root/.local/bin:$PATH"

WORKDIR /app

# Needed especially for post-install step
# cache files are 8GB
RUN pip install uv --no-cache-dir

RUN useradd -m -s /bin/bash pipelines_user

# For xvfb
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    chown -R root:root /tmp/.X11-unix

# Copy workspace manifests first for layer caching
COPY pyproject.toml uv.lock ./
COPY shared/pyproject.toml ./shared/pyproject.toml
COPY shared/src/shared ./shared/src/shared
COPY ${PROJECT_NAME}/pyproject.toml ./${PROJECT_NAME}/pyproject.toml

# Install deps for this workspace member
RUN uv sync --package pipelines --no-dev --frozen --no-install-project

# Copy source
COPY ${PROJECT_NAME}/src ./src

# ==========================================
# Stage: post-install
# ==========================================
FROM image-base AS post-install

RUN patchright install --with-deps chrome

RUN python -m spacy download en_core_web_md

USER pipelines_user

# ==========================================
# Final Stage: development
# ==========================================
FROM post-install AS development

ENV CIVICPATCH_ENV="development"

USER root
RUN apt-get update && apt-get install -y \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dev packages without blowing away spacy (we want to keep the previous spacy model)
# https://github.com/astral-sh/uv/issues/12481
RUN uv sync --inexact

WORKDIR /app

ENTRYPOINT ["/app/src/scripts/docker-entrypoint.sh"]
CMD ["fastapi", "dev", "src/server.py", "--host", "0.0.0.0", "--port", "8001"]

# ==========================================
# Final Stage: production
# ==========================================
FROM post-install AS production

ENV CIVICPATCH_ENV="production"

WORKDIR /app

USER root

RUN chown -R root:root /app && \
    chmod -R 755 /app

USER pipelines_user

ENTRYPOINT ["/app/src/scripts/docker-entrypoint.sh"]
