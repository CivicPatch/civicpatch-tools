# ==========================================
# Stage: image-base
# ==========================================
FROM python:3.12.11-slim-trixie AS image-base

RUN apt-get update && apt-get install -y \
    curl \
    xvfb \
    x11-utils \
    dbus-x11 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src" \
    PLAYWRIGHT_BROWSERS_PATH="/ms-playwright" \
    # Override for playwright to play nicely
    # with python 3.12-trixie
    # https://github.com/microsoft/playwright/issues/34255#issuecomment-2579839102
    # https://github.com/microsoft/playwright/blob/ef40dcbd59fcff11dde5eb6146e58ce3cccff1a4/packages/playwright-core/src/server/registry/index.ts#L231
    PLAYWRIGHT_HOST_PLATFORM_OVERRIDE="debian12-x64" \
    # Poetry setup with pip
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_HOME="/opt/poetry" \
    PATH="/opt/poetry/bin:$PATH" \
    POETRY_VIRTUALENVS_IN_PROJECT=false \
    # DEBUG="pw:browser" \
    XDG_CACHE_HOME="/tmp/.cache" \
    XDG_CONFIG_HOME="/tmp/.config" \
    PROJECT_NAME="civicpatch"

WORKDIR /app

# Needed especially for post-install step
# cache files are 8GB
RUN pip config set global.no-cache-dir true

RUN python3 -m venv $POETRY_HOME && \
    $POETRY_HOME/bin/pip install "poetry==2.1.3"

RUN useradd -m -s /bin/bash civicpatch_user

# For xvfb
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    mkdir -p /app/tmp/.cache && \
    mkdir -p /app/tmp/.config && \
    chown -R root:root /tmp/.X11-unix

RUN chown -R civicpatch_user:civicpatch_user /app/tmp/.cache /app/tmp/.config
COPY --chown=civicpatch_user:civicpatch_user ${PROJECT_NAME}/pyproject.toml ${PROJECT_NAME}/poetry.lock ./

# Copy the shared folder from parent directory
COPY --chown=civicpatch_user:civicpatch_user shared /app/src/shared

# Copy the rest of the application
COPY --chown=civicpatch_user:civicpatch_user ${PROJECT_NAME} /app

RUN poetry install

# ==========================================
# Stage: post-install
# ==========================================

FROM image-base AS post-install

RUN poetry run playwright install --with-deps chromium

COPY --chown=civicpatch_user:civicpatch_user ${PROJECT_NAME}/src/setup.py /app/src/setup.py
RUN poetry run post-install

USER civicpatch_user

#https://github.com/microsoft/playwright-python/issues/2572

# ==========================================
# Companion Stage: development-fe
# ==========================================

FROM node:24-slim AS development-fe

ENV NODE_ENV="development" \
    BUILD_ENV="development" \
    PROJECT_NAME="civicpatch"
WORKDIR /app

COPY --chown=civicpatch_user:civicpatch_user ${PROJECT_NAME}/src/frontend/package* /app
RUN npm install
COPY --chown=civicpatch_user:civicpatch_user ${PROJECT_NAME}/src/frontend/  /app

CMD ["npm", "run", "start"]

# ==========================================
# Final Stage: development
# ==========================================

# DEVELOPMENT IMAGE
FROM post-install AS development

ENV CIVICPATCH_ENV="development"

USER root
RUN apt-get update && apt-get install -y \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

USER civicpatch_user
EXPOSE 8000

ENTRYPOINT [ "/app/src/scripts/docker-entrypoint.sh" ]
CMD ["fastapi", "dev", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]
# Tmp change
# CMD ["fastapi", "run", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]

# ==========================================
# Stage: production-fe
# ==========================================

FROM node:24-slim AS production-build

ENV NODE_ENV="development" \
    BUILD_ENV="production" \
    PROJECT_NAME="civicpatch"
WORKDIR /app

RUN ls -la
COPY ${PROJECT_NAME}/src/frontend/package*.json /app
RUN npm install
COPY ${PROECT_NAME}/src/frontend/ /app

RUN ["npm", "run", "build"]

# ==========================================
# Final Stage: production
# ==========================================

# PRODUCTION IMAGE
FROM post-install AS production

ENV CIVICPATCH_ENV="production"

WORKDIR /app

COPY --from=production-build /app/dist/. /app/src/frontend/dist

USER civicpatch_user
EXPOSE 8000
# # Keep the container running
# CMD ["tail", "-f", "/dev/null"]
ENTRYPOINT [ "/app/src/scripts/docker-entrypoint.sh" ]
CMD ["fastapi", "run", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]
