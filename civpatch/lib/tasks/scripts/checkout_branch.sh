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
# Pull latest changes from the branch if it exists
git -C ./tmp/civicpatch-tools pull origin $BRANCH_NAME || true

# Copy everything except the lock files
cp -r ./tmp/civicpatch-tools/. /app

rm -rf ./tmp
cd /app/civpatch

# Create and checkout the branch in the main repo
git checkout -B $BRANCH_NAME
# Pull latest changes in the main repo
git pull origin $BRANCH_NAME || true
