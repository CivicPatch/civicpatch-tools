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

echo "Generating comment for $STATE $GEOID"
DATA=$(rake "github_pipeline:generate_comment[$STATE,$GEOID]")
COMMENT=$(printf "$DATA" | jq -r '.comment' | tr -d '"')

# Verify we got a valid comment
if [ -z "$COMMENT" ]; then
  echo "Error: Failed to generate comment for $STATE $GEOID"
  exit 1
fi

# Post the comment to the PR
gh pr comment $PR_NUMBER --edit-last --create-if-none --body "$COMMENT"
