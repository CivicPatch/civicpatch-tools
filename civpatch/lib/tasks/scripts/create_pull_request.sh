#!/bin/bash

set -e

STATE=$1
GEOID=$2

if [ -z "$STATE" ] || [ -z "$GEOID" ] ; then
  echo "Usage: $0 <state> <geoid>"
  echo "Found: state=${STATE} geoid=${GEOID}"
  exit 1
fi

echo "Creating pull request for $STATE $GEOID"
source "$(dirname "$0")/update_branch.sh" $STATE $GEOID

BRANCH_NAME=$(git branch --show-current)

PULL_REQUEST_DETAILS=$(rake "github_pipeline:pr_details[$STATE,$GEOID,$BRANCH_NAME]")

PR_TITLE=$(printf "$PULL_REQUEST_DETAILS" | jq '.pr_title' )
PR_BODY=$(printf "$PULL_REQUEST_DETAILS" | jq '.pr_body' )

if [[ -n $GITHUB_ENV ]]; then
  gh pr create --title "$PR_TITLE" --body "$PR_BODY" --label "$GITHUB_ENV" --base main
else
  gh pr create --title "$PR_TITLE" --body "$PR_BODY" --base main
fi
