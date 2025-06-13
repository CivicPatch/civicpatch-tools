#!/bin/bash

if [ -z "$BRANCH_NAME" ]; then
  echo "Environment variable BRANCH_NAME is not set"
  exit 1
fi

REPO_URL="https://github.com/CivicPatch/civicpatch-tools.git"

cd /app
mkdir -p ./tmp/civicpatch-tools
# Clone the specific branch directly
git clone -b $BRANCH_NAME $REPO_URL ./tmp/civicpatch-tools
# Ensure we have the latest
git -C ./tmp/civicpatch-tools pull origin $BRANCH_NAME

# Backup the lock files if they exist
[ -f civpatch/Gemfile.lock ] && cp civpatch/Gemfile.lock ./tmp/Gemfile.lock.backup
[ -f civpatch/package-lock.json ] && cp civpatch/package-lock.json ./tmp/package-lock.json.backup

# Copy everything except the lock files
cp -rn ./tmp/civicpatch-tools/. /app
# Overwrite civpatch/data and data_source with clobbering copy
cp -r ./tmp/civicpatch-tools/civpatch/data/. /app/civpatch/data/
cp -r ./tmp/civicpatch-tools/civpatch/data_source/. /app/civpatch/data_source/

# Restore the lock files if they existed
[ -f ./tmp/Gemfile.lock.backup ] && cp ./tmp/Gemfile.lock.backup /app/civpatch/Gemfile.lock
[ -f ./tmp/package-lock.json.backup ] && cp ./tmp/package-lock.json.backup /app/civpatch/package-lock.json

rm -rf ./tmp
cd /app/civpatch

# Ensure we're on the correct branch
git checkout $BRANCH_NAME
