FROM node:24-slim AS frontend-dev

WORKDIR /app

COPY api.civicpatch.org/src/frontend/package*.json /app/
RUN npm install

CMD ["npm", "start"]

FROM node:24-slim AS frontend-build

ENV NODE_ENV="development" BUILD_ENV="production"

WORKDIR /app

COPY api.civicpatch.org/src/frontend/package*.json /app/
RUN npm install
COPY api.civicpatch.org/src/frontend/ /app/
RUN npm run build

FROM python:3.12.11-slim-trixie AS image-base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    # For postgres
    libpq-dev gcc \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src" \
    PROJECT_NAME="api.civicpatch.org" \
    # uv: install packages into /venv
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_CACHE_DIR="/tmp/.cache/uv" \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON="/usr/local/bin/python3" \
    PATH="/venv/bin:/root/.local/bin:$PATH" \
    UV_VENV_SEED=1

WORKDIR /app

RUN pip install uv

# Copy workspace manifests first for layer caching
COPY pyproject.toml uv.lock ./
COPY shared/pyproject.toml ./shared/pyproject.toml
COPY ${PROJECT_NAME}/pyproject.toml ./${PROJECT_NAME}/pyproject.toml

# Install prod deps only (dev stage will reinstall with --dev)
RUN uv sync --package api.civicpatch.org --no-dev --frozen --no-install-project

# Copy source
COPY $PROJECT_NAME /app
COPY shared/src/shared /app/src/shared

COPY --from=frontend-build /app/build /app/src/frontend/build

RUN useradd -m -s /bin/bash civicpatch_user && \
    chown -R civicpatch_user:civicpatch_user /app && \
    chown -R civicpatch_user:civicpatch_user /venv

ENV PATH="/home/civicpatch_user/.local/bin:$PATH"

ENTRYPOINT ["/app/entrypoint.sh"]

# DEVELOPMENT IMAGE
FROM image-base AS development

ENV APP_ENVIRONMENT=development

# Reinstall with dev dependencies included
RUN uv sync --package api.civicpatch.org --frozen --no-install-project

WORKDIR /app
USER civicpatch_user
EXPOSE 8001
# CMD ["tail", "-f", "/dev/null"]
CMD ["fastapi", "dev", "src/main.py", "--port", "8001", "--host", "0.0.0.0"]

# PRODUCTION IMAGE
FROM image-base AS production

ENV APP_ENVIRONMENT=production

WORKDIR /app
USER civicpatch_user
EXPOSE 80
CMD ["fastapi", "run", "src/main.py", "--port", "80", "--host", "0.0.0.0", "--workers", "4"]
