#!/bin/bash

STATE_ARG=$1
GNIS_ARG=$2

if [ -z "$STATE_ARG" ]; then
  echo "Usage: $0 <state_code> <gnis_code>"
  exit 1
fi

if [ -z "$GNIS_ARG" ]; then
  echo "Usage: $0 <state_code> <gnis_code>"
  exit 1
fi

echo "Calling rake pipeline:fetch[$STATE_ARG,$GNIS_ARG]"

REPO_URL="https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com/CivicPatch/civicpatch-tools.git"

cd /app
mkdir -p ./tmp
git clone $REPO_URL ./tmp/civicpatch-tools --depth 1
cp -rn ./tmp/civicpatch-tools/. /app
rm -rf ./tmp
cd /app/civpatch

local_run_id=$(uuidgen)
branch_name="local-city-scrape-${STATE_ARG}-county-${GNIS_ARG}-${local_run_id}"
echo "Checking out new branch: ${branch_name}"
git checkout -b ${branch_name}




