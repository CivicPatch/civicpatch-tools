FROM python:3.11-slim AS image-base 
ENV PROJECT_NAME="civicpatch"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    xvfb \
    x11-utils \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    VIRTUAL_ENV="/venv" \
    PYTHONPATH=/app/src \
    # Set compatible path for both root & non-root users
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Add Poetry and virtual env to PATH
ENV PATH="$POETRY_HOME/bin:$VIRTUAL_ENV/bin:$PATH"

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Prepare virtual env
RUN python -m venv $VIRTUAL_ENV

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

RUN chown -R civicpatch_user:civicpatch_user /venv

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