#!/bin/bash

if [ -z "$BRANCH_NAME" ]; then
  echo "Environment variable BRANCH_NAME is not set"
  exit 1
fi

REPO_URL="https://github.com/CivicPatch/civicpatch-tools.git"

cd /app
mkdir -p ./tmp/civicpatch-tools
# https://git-scm.com/docs/git#_options
git clone -b main $REPO_URL ./tmp/civicpatch-tools
git -C ./tmp/civicpatch-tools fetch origin $BRANCH_NAME || true  
git -C ./tmp/civicpatch-tools checkout -B $BRANCH_NAME
git -C ./tmp/civicpatch-tools pull origin $BRANCH_NAME || true

# Don't overwrite things like Gemfile.lock, package-lock.json, etc. from
# the Dockerfile.
cp -rn ./tmp/civicpatch-tools/. /app
# Overwrite civpatch/data and data_source with clobbering copy
cp -r ./tmp/civicpatch-tools/civpatch/data/. /app/civpatch/data/
cp -r ./tmp/civicpatch-tools/civpatch/data_source/. /app/civpatch/data_source/

rm -rf ./tmp
cd /app/civpatch

git checkout -B ${BRANCH_NAME}
