#!/bin/bash

STATE_ARG=$1
GNIS_ARG=$2
CREATE_PR_ARG=${3:-false}
SEND_COSTS_ARG=${4:-false}

if [ -z "$STATE_ARG" ]; then
  echo "Usage: $0 <state_code> <gnis_code>"
  exit 1
fi

if [ -z "$GNIS_ARG" ]; then
  echo "Usage: $0 <state_code> <gnis_code>"
  exit 1
fi

echo "Calling rake pipeline:fetch[$STATE_ARG,$GNIS_ARG,$CREATE_PR_ARG,$SEND_COSTS_ARG]"

REPO_URL="https://${GITHUB_TOKEN}@github.com/CivicPatch/civicpatch-tools.git"

cd /app
mkdir -p ./tmp
git config --global user.name "$GITHUB_USERNAME"
git config --global user.email "civicpatch-tools@civicpatch.org"
# https://git-scm.com/docs/git#_options
git -C ./tmp/civicpatch-tools remote set-url origin $REPO_URL
git clone -b main --single-branch $REPO_URL ./tmp/civicpatch-tools

cp -rn ./tmp/civicpatch-tools/. /app
rm -rf ./tmp
cd /app/civpatch

local_run_id=$(uuidgen)
branch_name="local-city-scrape-${STATE_ARG}-county-${GNIS_ARG}-${local_run_id}"
echo "Checking out new branch: ${branch_name}"
git checkout -b ${branch_name}




