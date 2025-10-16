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
    # DEBUG="pw:browser" \
    XDG_CACHE_HOME="/app/tmp/.cache" \
    XDG_CONFIG_HOME="/app/tmp/.config" 

RUN mkdir -p /app/tmp

# Needed especially for post-install step
# cache files are 8GB
RUN pip config set global.no-cache-dir true

RUN python3 -m venv $POETRY_HOME && \
    $POETRY_HOME/bin/pip install "poetry==2.1.3"

WORKDIR /app

# COPY ./utils /app/utils

RUN useradd -m -s /bin/bash civicpatch_user

# For xvfb
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix && \
    mkdir -p /app/tmp/.cache && \
    mkdir -p /app/tmp/.config && \
    chown -R root:root /tmp/.X11-unix

RUN chown -R civicpatch_user:civicpatch_user /app/tmp/.cache /app/tmp/.config
COPY --chown=civicpatch_user:civicpatch_user pyproject.toml poetry.lock ./
COPY --chown=civicpatch_user:civicpatch_user . /app

RUN poetry install

FROM image-base AS post-install

RUN poetry run playwright install --with-deps chromium

COPY --chown=civicpatch_user:civicpatch_user src/setup.py /app/src/setup.py
RUN poetry run post-install

USER civicpatch_user

#https://github.com/microsoft/playwright-python/issues/2572
ENTRYPOINT [ "/app/src/scripts/docker-entrypoint.sh" ]

# DEVELOPMENT IMAGE
FROM post-install AS development

USER root
RUN apt-get update && apt-get install -y \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

USER civicpatch_user
EXPOSE 8000

CMD ["fastapi", "dev", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]

# PRODUCTION IMAGE
FROM post-install AS production

WORKDIR /app

USER civicpatch_user
EXPOSE 8000
# # Keep the container running
# CMD ["tail", "-f", "/dev/null"]
CMD ["fastapi", "run", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]