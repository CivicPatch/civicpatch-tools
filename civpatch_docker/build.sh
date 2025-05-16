#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
IMAGE_NAME="your-image-name" # Replace with your actual image name

# Use RELEASE_VERSION from environment if set, otherwise default to "latest"
VERSION="${RELEASE_VERSION:-latest}"

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Assume Dockerfile is in the same directory as the script
DOCKERFILE_PATH="${SCRIPT_DIR}/Dockerfile"
CONTEXT_PATH="${SCRIPT_DIR}" # Or specify another context path if needed

# --- Build ---
echo "Building Docker image: ${IMAGE_NAME}:${VERSION}"
echo "Dockerfile: ${DOCKERFILE_PATH}"
echo "Build Context: ${CONTEXT_PATH}"

docker build -t "${IMAGE_NAME}:${VERSION}" -f "${DOCKERFILE_PATH}" "${CONTEXT_PATH}"

echo "Docker image built successfully: ${IMAGE_NAME}:${VERSION}"

# --- (Optional) Add more tags ---
# For example, if you also want to tag it as "latest" regardless of the VERSION
if [ "${VERSION}" != "latest" ]; then
  echo "Additionally tagging as ${IMAGE_NAME}:latest"
  docker tag "${IMAGE_NAME}:${VERSION}" "${IMAGE_NAME}:latest"
fi

# If VERSION is a semantic version like x.y.z, also tag as x.y
if [[ "$VERSION" =~ ^[0-9]+\\.[0-9]+\\.[0-9]+$ ]]; then
  MAJOR_MINOR_VERSION=$(echo "$VERSION" | cut -d. -f1,2)
  echo "Additionally tagging with major-minor version: ${IMAGE_NAME}:${MAJOR_MINOR_VERSION}"
  docker tag "${IMAGE_NAME}:${VERSION}" "${IMAGE_NAME}:${MAJOR_MINOR_VERSION}"

  # Example: If you also have a registry prefix you want to add for all specific versions
  # REGISTRY_PREFIX="yourdockerhubusername/" # Uncomment and set if needed
  # if [ -n "$REGISTRY_PREFIX" ]; then
  #   echo "Additionally tagging for registry: ${REGISTRY_PREFIX}${IMAGE_NAME}:${VERSION}"
  #   docker tag "${IMAGE_NAME}:${VERSION}" "${REGISTRY_PREFIX}${IMAGE_NAME}:${VERSION}"
  #   echo "Additionally tagging for registry (major-minor): ${REGISTRY_PREFIX}${IMAGE_NAME}:${MAJOR_MINOR_VERSION}"
  #   docker tag "${IMAGE_NAME}:${VERSION}" "${REGISTRY_PREFIX}${IMAGE_NAME}:${MAJOR_MINOR_VERSION}"
  # fi
fi

echo "Build complete." 
