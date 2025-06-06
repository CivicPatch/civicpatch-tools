#!/bin/bash

if [ -z "$BRANCH_NAME" ]; then
  echo "Environment variable BRANCH_NAME is not set"
  exit 1
fi

REPO_URL="https://github.com/CivicPatch/civicpatch-tools.git"

APP_DIR="/app"

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

if [ ! -d "$APP_DIR/.git" ]; then
  echo "No existing Git repository found at $APP_DIR. Performing initial clone..."
  # Use --depth 1 for faster, smaller clones if full history isn't needed
  git clone --depth 1 -b "$BRANCH_NAME" "$REPO_URL" "$APP_DIR" || { echo "ERROR: Git clone failed!"; exit 1; }
  echo "Initial clone complete."
else
  # If a Git repo exists, update it.
  echo "Existing Git repository found at $APP_DIR. Updating..."

  cd "$APP_DIR"

  # Ensure the target branch exists locally (create if not) and checkout
  # -B creates/resets the branch to the remote's state
  echo "Checking out/resetting local branch $BRANCH_NAME to origin/$BRANCH_NAME..."
  git checkout -B "$BRANCH_NAME" "origin/$BRANCH_NAME" || { echo "ERROR: Git checkout failed!"; exit 1; }

  echo "Fetching latest changes from origin..."
  git fetch origin || { echo "ERROR: Git fetch failed!"; exit 1; }

  echo "Pulling latest changes for branch $BRANCH_NAME..."
  git pull origin "$BRANCH_NAME" || { echo "ERROR: Git pull failed!"; exit 1; }

  echo "Repository update complete."
fi
