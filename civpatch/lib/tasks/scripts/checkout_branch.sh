#!/bin/bash

#STATE_ARG=$1
#GNIS_ARG=$2
#BRANCH_NAME=$1

#if [ -z "$STATE_ARG" ]; then
#  echo "Usage: $0 <state_code> <gnis_code>"
#  exit 1
#fi
#
#if [ -z "$GNIS_ARG" ]; then
#  echo "Usage: $0 <state_code> <gnis_code>"
#  exit 1
#fi

if [ -z "$BRANCH_NAME" ]; then
  echo "Environment variable BRANCH_NAME is not set"
  exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
  echo "Environment variable GITHUB_TOKEN is not set"
  exit 1
fi

if [ -z "$GITHUB_USERNAME" ]; then
  echo "Environment variable GITHUB_USERNAME is not set"
  exit 1
fi

REPO_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/CivicPatch/civicpatch-tools.git"

cd /app
mkdir -p ./tmp/civicpatch-tools
git config --global user.name "$GITHUB_USERNAME"
git config --global user.email "civicpatch-tools@civicpatch.org"
# https://git-scm.com/docs/git#_options
git clone -b main --single-branch $REPO_URL ./tmp/civicpatch-tools
git -C ./tmp/civicpatch-tools remote set-url origin $REPO_URL

cp -rn ./tmp/civicpatch-tools/. /app
rm -rf ./tmp
cd /app/civpatch

#if [ -z "$BRANCH_NAME" ]; then
#  local_run_id=$(uuidgen)
#  branch_name="pipeline-municipal-scrapes-${STATE_ARG}-${GNIS_ARG}-${local_run_id}"
#  echo "Checking out new branch: ${branch_name}"
#  git checkout -b ${branch_name}
#else
#  echo "Using existing branch: ${BRANCH_NAME}"
#  git checkout ${BRANCH_NAME}
#fi

git checkout -B ${BRANCH_NAME}
