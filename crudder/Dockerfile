FROM python:3.11-bullseye AS image-base 
ENV PROJECT_NAME="crudder"

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
    PYTHONPATH=/app/src

# Add Poetry and virtual env to PATH
ENV PATH="$POETRY_HOME/bin:$VIRTUAL_ENV/bin:$PATH"

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Prepare virtual env
RUN python -m venv $VIRTUAL_ENV

WORKDIR /app
COPY ${PROJECT_NAME}/pyproject.toml ${PROJECT_NAME}/poetry.lock ./
RUN poetry install --no-root

COPY ./shared /app/shared
COPY ./${PROJECT_NAME} /app

# DEVELOPMENT IMAGE
FROM image-base AS development

ENV APP_ENVIRONMENT=development

WORKDIR /app

RUN useradd -m -s /bin/bash civicpatch_user
RUN chown -R civicpatch_user:civicpatch_user /app
RUN chown -R civicpatch_user:civicpatch_user /venv

USER civicpatch_user

# CMD ["tail", "-f", "/dev/null"]
CMD ["fastapi", "dev", "src/main.py", "--port", "8001", "--host", "0.0.0.0"]

# PRODUCTION IMAGE
FROM image-base AS production 

ENV APP_ENVIRONMENT=production

WORKDIR /app

RUN useradd -m -s /bin/bash civicpatch_user
RUN chown -R civicpatch_user:civicpatch_user /app

USER civicpatch_user
# # Keep the container running
CMD ["fastapi", "run", "src/main.py", "--port", "80", "--host", "0.0.0.0"]