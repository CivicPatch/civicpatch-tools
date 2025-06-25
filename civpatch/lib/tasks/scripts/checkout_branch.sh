#!/bin/bash

if [ -z "$BRANCH_NAME" ]; then
  echo "Environment variable BRANCH_NAME is not set"
  exit 1
fi

REPO_URL="https://github.com/CivicPatch/civicpatch-tools.git"

cd /app

# Clone the repository into the current directory
git clone -b $BRANCH_NAME $REPO_URL . || {
  echo "Failed to clone branch $BRANCH_NAME. Falling back to main branch."
  git clone -b main $REPO_URL .
}

# Checkout the target branch (create it if it doesn't exist locally)
git checkout -B $BRANCH_NAME origin/$BRANCH_NAME || git checkout -B $BRANCH_NAME

mv /tmp/civpatch/node_modules /app/civpatch/node_modules || {
  echo "Failed to restore node_modules from /tmp/node_modules"
  exit 1
}