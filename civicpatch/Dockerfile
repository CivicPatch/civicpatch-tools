FROM ubuntu:noble AS image-base 
ENV PROJECT_NAME="civicpatch"

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Mise setup
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV MISE_DATA_DIR="/mise"
ENV MISE_CONFIG_DIR="/mise"
ENV MISE_CACHE_DIR="/mise/cache"
ENV MISE_INSTALL_PATH="/usr/local/bin/mise"
ENV PATH="/mise/shims:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    xvfb \
    x11-utils \
    git \
    # For mise
    ca-certificates build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://mise.run | sh

RUN mise use python@3.11
RUN mise use poetry@2.1.3


WORKDIR /app

COPY ${PROJECT_NAME}/pyproject.toml ${PROJECT_NAME}/poetry.lock ./
RUN poetry install --no-root

# COPY ./utils /app/utils

RUN useradd -m -s /bin/bash civicpatch_user
RUN chown -R civicpatch_user:civicpatch_user /app

FROM image-base AS post-install-stage

COPY ${PROJECT_NAME}/src/setup.py /app/src/setup.py
RUN poetry run post-install

#https://github.com/microsoft/playwright-python/issues/2572
USER root
ENTRYPOINT [ "/app/src/scripts/docker-entrypoint.sh" ]

# DEVELOPMENT IMAGE
FROM post-install-stage AS development

RUN apt-get update && apt-get install -y \
    vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

USER civicpatch_user
EXPOSE 8000

CMD ["fastapi", "dev", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]

# PRODUCTION IMAGE
FROM post-install-stage AS production 

WORKDIR /app

COPY ./${PROJECT_NAME} /app
COPY ./data /app/data
COPY ./data_source /app/data_source

USER civicpatch_user
EXPOSE 8000
# # Keep the container running
# CMD ["tail", "-f", "/dev/null"]
CMD ["fastapi", "run", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]