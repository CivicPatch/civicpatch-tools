# Use an official Python image as the base
FROM python:3.11-bullseye

# Set the working directory in the container
WORKDIR /app

ENV PYTHONPATH=/app/src

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - --version 2.1.3

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy project files into the container
COPY . /app

# Install project dependencies
RUN poetry install --no-root

RUN poetry run playwright install-deps

RUN poetry run post-install

# Keep the container running
CMD ["tail", "-f", "/dev/null"]