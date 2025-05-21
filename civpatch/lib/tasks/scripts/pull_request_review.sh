#!/bin/bash

STATE=$1
GEOID=$2
PR_NUMBER=$3

if [ -z "$STATE" ] || [ -z "$GEOID" ] || [ -z "$PR_NUMBER" ]; then
  echo "Usage: $0 <state> <geoid> <pr_number>"
  echo "Found: state=${STATE} geoid=${GEOID} pr_number=${PR_NUMBER}"
  exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
  echo "GITHUB_TOKEN is not set; required for commenting on PRs"
  exit 1
fi

if [ -z "$GH_TOKEN" ]; then
  echo "GH_TOKEN is not set; required for commenting on PRs"
  exit 1
fi

REVIEW=$(rake github_pipeline:generate_review[$STATE,$GEOID])
echo $REVIEW
SCORE=$(printf '%b' "$REVIEW" | jq -r '.score')
COMMENT=$(printf '%b' "$REVIEW" | jq -r '.comment')





# gh pr comment $PR_NUMBER --edit-last --create-if-none --body "$COMMENT"
