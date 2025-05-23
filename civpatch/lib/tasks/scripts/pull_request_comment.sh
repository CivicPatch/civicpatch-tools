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

# Get the JSON output, parse it with jq, and format with awk
COMMENT=$(rake github_pipeline:generate_comment[$STATE,$GEOID] | jq -r '.comment' | awk '{printf "%s\\n", $0}')

# Verify we got a valid comment
if [ -z "$COMMENT" ]; then
  echo "Error: Failed to generate comment"
  exit 1
fi

# Post the comment to the PR
gh pr comment $PR_NUMBER --edit-last --create-if-none --body "$COMMENT"
