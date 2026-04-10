FROM python:3.12.11-slim-trixie

RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/src" \
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_CACHE_DIR="/tmp/.cache/uv" \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON="/usr/local/bin/python3" \
    PATH="/venv/bin:/root/.local/bin:$PATH" \
    UV_VENV_SEED=1

WORKDIR /app

RUN pip install uv

# Copy workspace manifests for layer caching
COPY pyproject.toml uv.lock ./
COPY shared/pyproject.toml ./shared/pyproject.toml
COPY worker/pyproject.toml ./worker/pyproject.toml

RUN uv sync --package worker --frozen --no-install-project --extra dev

# Copy source
COPY worker/src /app/src
COPY shared/src/shared /app/src/shared

CMD ["python", "src/main.py"]
