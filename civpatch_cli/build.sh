#!/bin/bash

# build.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "${SCRIPT_DIR}"

OUTPUT_DIR="../dist" 
APP_NAME="civpatch_cli"
MAIN_PACKAGE="."

if [ -z "${RELEASE_VERSION}" ]; then
    echo "RELEASE_VERSION must be set"
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

build_for_platform() {
    local os="$1"
    local arch="$2"
    local friendly_name="$3"
    local output_name="${APP_NAME}-${RELEASE_VERSION}-${friendly_name}"

    if [ "${os}" == "windows" ]; then
        output_name+=".exe"
    fi

    echo "Building for ${os}/${arch}..."
    env GOOS="${os}" GOARCH="${arch}" go build -ldflags="-X main.Version=${RELEASE_VERSION}" -o "${OUTPUT_DIR}/${output_name}" "${MAIN_PACKAGE}"
    if [ $? -eq 0 ]; then
        echo "Successfully built ${OUTPUT_DIR}/${output_name}"
    else
        echo "Failed to build for ${os}/${arch}"
        exit 1
    fi
}

# Build for common platforms
build_for_platform "linux" "amd64" "linux-amd64"
build_for_platform "linux" "arm64" "linux-arm64"
build_for_platform "windows" "amd64" "windows-amd64.exe"
build_for_platform "darwin" "amd64" "macos-intel"
build_for_platform "darwin" "arm64" "macos-apple-silicon"

# Example: Build for a specific target if arguments are provided
# if [ "$1" != "" ] && [ "$2" != "" ]; then
#    build_for_platform "$1" "$2"
# else
#    # Build for common platforms (as above)
# fi

echo "All builds finished."
