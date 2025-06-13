#!/bin/bash

if [ -z "$BRANCH_NAME" ]; then
  echo "Environment variable BRANCH_NAME is not set"
  exit 1
fi

REPO_URL="https://github.com/CivicPatch/civicpatch-tools.git"

cd /app
mkdir -p ./tmp/civicpatch-tools
# Clone main branch first
git clone -b main $REPO_URL ./tmp/civicpatch-tools
# Try to fetch the target branch
git -C ./tmp/civicpatch-tools fetch origin $BRANCH_NAME || true
# Create and checkout the branch (will create if doesn't exist)
git -C ./tmp/civicpatch-tools checkout -B $BRANCH_NAME

# Backup the lock files if they exist
[ -f civpatch/Gemfile.lock ] && cp civpatch/Gemfile.lock ./tmp/Gemfile.lock.backup
[ -f civpatch/package-lock.json ] && cp civpatch/package-lock.json ./tmp/package-lock.json.backup

# Copy everything except the lock files
cp -rn ./tmp/civicpatch-tools/. /app
# Overwrite civpatch/data and data_source with clobbering copy if they exist
[ -d ./tmp/civicpatch-tools/civpatch/data ] && cp -r ./tmp/civicpatch-tools/civpatch/data/. /app/civpatch/data/
[ -d ./tmp/civicpatch-tools/civpatch/data_source ] && cp -r ./tmp/civicpatch-tools/civpatch/data_source/. /app/civpatch/data_source/

# Restore the lock files if they existed
[ -f ./tmp/Gemfile.lock.backup ] && cp ./tmp/Gemfile.lock.backup /app/civpatch/Gemfile.lock
[ -f ./tmp/package-lock.json.backup ] && cp ./tmp/package-lock.json.backup /app/civpatch/package-lock.json

rm -rf ./tmp
cd /app/civpatch

# Create and checkout the branch in the main repo
git checkout -B $BRANCH_NAME
