#!/bin/bash

set -e

GITHUB_TOKEN=${GITHUB_TOKEN}
GITHUB_USERNAME=${GITHUB_USERNAME}

if [[ ${PUSH_IMAGE} == "true" ]]; then
  if [ -z "${GITHUB_TOKEN}" ] || [ -z "${GITHUB_USERNAME}" ]; then
    echo "GITHUB_TOKEN and GITHUB_USERNAME must be set"
    exit 1
  fi
fi

if [ -z "${RELEASE_VERSION}" ]; then
  echo "RELEASE_VERSION must be set"
  exit 1
fi

if [ -z "${IMAGE_NAME}" ]; then
  echo "IMAGE_NAME must be set"
  exit 1
fi

DOCKERFILE_PATH="./Dockerfile.civpatch"
BUILD_CONTEXT="." 
REGISTRY_HOST="ghcr.io"

BUILD_ARGS="" # No extra ldbuild args by default

# --- Main Build Logic ---
echo "Building Docker image: ${IMAGE_NAME} with tag: ${RELEASE_VERSION}"
echo "Dockerfile: ${DOCKERFILE_PATH}"
echo "Build Context: ${BUILD_CONTEXT}"
if [ -n "${BUILD_ARGS}" ]; then
  echo "Build Args: ${BUILD_ARGS}"
fi

# The Docker build command
docker build ${BUILD_ARGS} -t "${IMAGE_NAME}:${RELEASE_VERSION}" -t "${IMAGE_NAME}:latest" -f "${DOCKERFILE_PATH}" "${BUILD_CONTEXT}"

echo ""
echo "Docker image built successfully: ${IMAGE_NAME}:${RELEASE_VERSION}"

if [ -n "${PUSH_IMAGE}" ]; then
  echo $GITHUB_TOKEN | docker login -u$GITHUB_USERNAME --password-stdin $REGISTRY_HOST
  echo "Pushing image ${IMAGE_NAME}:${RELEASE_VERSION}..."
  docker push --all-tags "${IMAGE_NAME}"
  echo "Image pushed successfully."
else
  echo "Image not pushed."
fi

exit 0
