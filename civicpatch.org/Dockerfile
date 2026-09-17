FROM node:24-slim AS frontend-dev

WORKDIR /app

COPY civicpatch.org/src/frontend/package*.json /app/
RUN npm install

CMD ["npm", "start"]

FROM node:24-slim AS frontend-build

WORKDIR /app

COPY civicpatch.org/src/frontend/package*.json /app/
RUN npm install
COPY civicpatch.org/src/frontend/ /app/
RUN npm run typecheck
RUN npm run build

FROM python:3.12.11-slim-trixie AS image-base

# `curl` only: psycopg ships its own libpq (the `[binary]` extra), and every dependency installs
# from a wheel, so the compiler and headers the image used to carry built nothing.
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src" \
    PROJECT_NAME="civicpatch.org" \
    # uv: install packages into /venv
    UV_PROJECT_ENVIRONMENT="/venv" \
    # No cache: the downloaded wheels are build scratch, and a cache dir inside the image was
    # ~990MB of it.
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON="/usr/local/bin/python3" \
    PATH="/venv/bin:/root/.local/bin:$PATH" \
    UV_VENV_SEED=1

WORKDIR /app

# The binary, not a pip install into the image's own Python: `pip install uv` was an 81MB layer.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /usr/local/bin/

# Before anything is written: a `chown -R` afterwards rewrites every file it touches into a new
# layer, which cost a second ~1GB copy of /venv. Owning the empty dirs and copying with --chown
# keeps each file in exactly one layer.
RUN useradd -m -s /bin/bash civicpatch_user && \
    mkdir -p /venv /app && \
    chown civicpatch_user:civicpatch_user /venv /app

USER civicpatch_user

# Copy workspace manifests first for layer caching
COPY --chown=civicpatch_user:civicpatch_user pyproject.toml uv.lock ./
COPY --chown=civicpatch_user:civicpatch_user shared/pyproject.toml ./shared/pyproject.toml
COPY --chown=civicpatch_user:civicpatch_user ${PROJECT_NAME}/pyproject.toml ./${PROJECT_NAME}/pyproject.toml

# Install prod deps only (dev stage will reinstall with --dev)
RUN uv sync --package civicpatch.org --no-dev --frozen --no-install-project

# Copy source
COPY --chown=civicpatch_user:civicpatch_user $PROJECT_NAME /app
COPY --chown=civicpatch_user:civicpatch_user shared/src/shared /app/src/shared

COPY --from=frontend-build --chown=civicpatch_user:civicpatch_user /app/build /app/src/frontend/build

ENV PATH="/home/civicpatch_user/.local/bin:$PATH"

ENTRYPOINT ["/app/entrypoint.sh"]

# DEVELOPMENT IMAGE
FROM image-base AS development

ENV APP_ENVIRONMENT=development

# Reinstall with dev dependencies included
RUN uv sync --package civicpatch.org --frozen --no-install-project

WORKDIR /app
USER civicpatch_user
EXPOSE 8000
# CMD ["tail", "-f", "/dev/null"]
CMD ["fastapi", "dev", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]

# PRODUCTION IMAGE
FROM image-base AS production

ENV APP_ENVIRONMENT=production

WORKDIR /app
USER civicpatch_user
EXPOSE 80
CMD ["fastapi", "run", "src/main.py", "--port", "80", "--host", "0.0.0.0", "--workers", "4"]
