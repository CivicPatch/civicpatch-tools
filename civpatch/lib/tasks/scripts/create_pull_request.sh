#!/bin/bash

set -e

STATE=$1
GEOID=$2
BRANCH_NAME=$3

if [ -z "$STATE" ] || [ -z "$GEOID" ] || [ -z "$BRANCH_NAME" ] ; then
  echo "Usage: $0 <state> <geoid> <branch_name>"
  echo "Found: state=${STATE} geoid=${GEOID} branch_name=${BRANCH_NAME}"
  exit 1
fi

echo "Creating pull request for $STATE $GEOID"
source "$(dirname "$0")/update_branch.sh" $STATE $GEOID

PULL_REQUEST_DETAILS=$(rake "github_pipeline:pr_details[$STATE,$GEOID]")

PR_TITLE=$(printf "$PULL_REQUEST_DETAILS" | jq '.pr_title' )
PR_BODY=$(printf "$PULL_REQUEST_DETAILS" | jq '.pr_body' )
HEAD="$GITHUB_USER:$BRANCH_NAME"

if [[ -n $GITHUB_ENV ]]; then
  gh pr create --title "$PR_TITLE" --body "$PR_BODY" --label "$GITHUB_ENV" --head "$HEAD"
else
  gh pr create --title "$PR_TITLE" --body "$PR_BODY" --head "$HEAD"
fi
