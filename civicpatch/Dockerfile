FROM python:3.11-bullseye AS image-base 
ENV PROJECT_NAME="civicpatch"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    xvfb \
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
RUN poetry run playwright install-deps
RUN poetry run playwright install chromium

COPY ./${PROJECT_NAME} /app
COPY ./shared /app/shared

RUN poetry run post-install

#https://github.com/microsoft/playwright-python/issues/2572
ENV DISPLAY=:99
ENTRYPOINT [ "/app/src/scripts/docker-entrypoint.sh" ]

RUN useradd -m -s /bin/bash civicpatch_user
RUN chown -R civicpatch_user:civicpatch_user /app

# DEVELOPMENT IMAGE
FROM image-base AS development

WORKDIR /app

RUN chown -R civicpatch_user:civicpatch_user /venv
USER civicpatch_user

CMD ["fastapi", "dev", "src/main.py", "--port", "8000", "--host", "0.0.0.0"]

# PRODUCTION IMAGE
FROM image-base AS production 

WORKDIR /app

USER civicpatch_user
# # Keep the container running
# CMD ["tail", "-f", "/dev/null"]
CMD ["fastapi", "run", "src/main.py", "--port", "80", "--host", "0.0.0.0"]