#!/bin/bash

set -e

STATE=$1
GEOID=$2

if [ -z "$STATE" ] || [ -z "$GEOID" ] ; then
  echo "Usage: $0 <state> <geoid>"
  echo "Found: state=${STATE} geoid=${GEOID}"
  exit 1
fi

source "$(dirname "$0")/update_branch.sh" $STATE $GEOID

PULL_REQUEST_DETAILS=$(rake "github_pipeline:pr_details[$STATE,$GEOID]")

PR_TITLE=$(printf "$PULL_REQUEST_DETAILS" | jq '.pr_title' )
PR_BODY=$(printf "$PULL_REQUEST_DETAILS" | jq '.pr_body' )

if [[ -n $GITHUB_ENV ]]; then
  gh pr create --title "$PR_TITLE" --body "$PR_BODY" --label "$GITHUB_ENV"
else
  gh pr create --title "$PR_TITLE" --body "$PR_BODY"
fi
