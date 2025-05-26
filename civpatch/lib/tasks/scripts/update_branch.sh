#!/bin/bash

set -e

STATE=$1
GEOID=$2

if [ -z "$STATE" ] || [ -z "$GEOID" ]; then
  echo "Usage: $0 <state> <geoid>"
  echo "Found: state=${STATE} geoid=${GEOID}"
  exit 1
fi

FOLDERS_TO_COPY=(
  "/app/civpatch/config"
  "/app/civpatch/data"
  "/app/civpatch/data_source"
)

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ "$CURRENT_BRANCH" == "main" ]]; then
  echo "Cannot update the main branch!"
  exit 1;
fi

COMMIT_MESSAGE="Municipality officials scrape for state: $STATE geoid: $GEOID"

echo "Committing changes (if any) to branch ($CURRENT_BRANCH): ${FOLDERS_TO_COPY[@]}"

git add "${FOLDERS_TO_COPY[@]}"
git commit -m "$COMMIT_MESSAGE"
git push -u origin $CURRENT_BRANCH
