#!/bin/bash

# build.sh

set -e # Exit immediately if a command exits with a non-zero status.

# Default output directory
OUTPUT_DIR="../dist"
# Name of your main Go package/executable
APP_NAME="civpatch_cli"
# Path to your main package
MAIN_PACKAGE="." # Or ./cmd/mygoapp, etc.
# Opt for dates instead of semver
VERSION=$(date +%Y-%m-%d)

echo "Listing files in $(pwd):"


# Create output directory if it doesn't exist
mkdir -p "${OUTPUT_DIR}"

# Function to build for a specific platform
build_for_platform() {
    local os="$1"
    local arch="$2"
    local output_name="${APP_NAME}-${VERSION}-${os}-${arch}"

    if [ "${os}" == "windows" ]; then
        output_name+=".exe"
    fi

    echo "Building for ${os}/${arch}..."
    env GOOS="${os}" GOARCH="${arch}" go build -ldflags="-X main.Version=${VERSION}" -o "${OUTPUT_DIR}/${output_name}" "${MAIN_PACKAGE}"
    if [ $? -eq 0 ]; then
        echo "Successfully built ${OUTPUT_DIR}/${output_name}"
    else
        echo "Failed to build for ${os}/${arch}"
        exit 1
    fi
}

# Build for common platforms
build_for_platform "linux" "amd64"
build_for_platform "linux" "arm64"
build_for_platform "windows" "amd64"
build_for_platform "darwin" "amd64" # For Intel Macs
build_for_platform "darwin" "arm64" # For Apple Silicon Macs

# Example: Build for a specific target if arguments are provided
# if [ "$1" != "" ] && [ "$2" != "" ]; then
#    build_for_platform "$1" "$2"
# else
#    # Build for common platforms (as above)
# fi

echo "All builds finished."
