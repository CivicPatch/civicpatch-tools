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
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_VIRTUALENVS_IN_PROJECT=false \
    VIRTUAL_ENV="/venv" \
    PYTHONPATH=/app/src \
    PROJECT_NAME="api.civicpatch.org"

# Add Poetry and virtual env to PATH
ENV PATH="$POETRY_HOME/bin:$VIRTUAL_ENV/bin:$PATH"

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Prepare virtual env
RUN python -m venv $VIRTUAL_ENV

WORKDIR /app
COPY $PROJECT_NAME/pyproject.toml $PROJECT_NAME/poetry.lock ./
RUN poetry install --no-root

COPY $PROJECT_NAME /app
COPY civicpatch/src/schemas.py /app/src/civicpatch/schemas.py
COPY civicpatch/src/utils/id_utils.py /app/src/civicpatch/id_utils.py
RUN mkdir -p /app/git_data

RUN useradd -m -s /bin/bash civicpatch_user
RUN chown -R civicpatch_user:civicpatch_user /app

ENV PATH="/home/civicpatch_user/.local/bin:$PATH"

ENTRYPOINT ["/app/entrypoint.sh"]

# DEVELOPMENT IMAGE
FROM image-base AS development

ENV APP_ENVIRONMENT=development

WORKDIR /app

RUN chown -R civicpatch_user:civicpatch_user /venv

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

CMD ["fastapi", "run", "src/main.py", "--port", "80", "--host", "0.0.0.0"]
