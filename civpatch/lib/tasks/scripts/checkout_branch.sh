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

cp -rn ./tmp/civicpatch-tools/. /app
rm -rf ./tmp
cd /app/civpatch

git checkout -B ${BRANCH_NAME}
