#!/bin/bash

set -e

STATE=$1
GEOID=$2

if [ -z "$GITHUB_TOKEN" ]; then
  echo "Environment variable GITHUB_TOKEN is not set"
  exit 1
fi

if [ -z "$GITHUB_USERNAME" ]; then
  echo "Environment variable GITHUB_USERNAME is not set"
  exit 1
fi

if [ -z "$STATE" ] || [ -z "$GEOID" ]; then
  echo "Usage: $0 <state> <geoid>"
  echo "Found: state=${STATE} geoid=${GEOID}"
  exit 1
fi

FOLDERS_TO_COPY=(
  "./config"
  "./data"
  "./data_source"
)

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [[ "$CURRENT_BRANCH" == "main" ]]; then
  echo "Cannot update the main branch!"
  exit 1;
fi

COMMIT_MESSAGE="Municipality officials scrape for state: $STATE geoid: $GEOID"

echo "Committing changes (if any) to branch ($CURRENT_BRANCH): ${FOLDERS_TO_COPY[@]}"

REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/CivicPatch/civicpatch-tools.git"
git remote set-url origin $REPO_URL

git config --global user.name "$GITHUB_USERNAME"
git config --global user.email "civicpatch-tools@civicpatch.org"

git add "${FOLDERS_TO_COPY[@]}"
git commit -m "$COMMIT_MESSAGE"
git push -u origin $CURRENT_BRANCH
