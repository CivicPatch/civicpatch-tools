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

REVIEW=$(rake "github_pipeline:generate_review[$STATE,$GEOID]")
SCORE=$(printf "$REVIEW" | jq '.score' )
COMMENT=$(printf "$REVIEW" | jq --raw-output '.comment' | tr -d '"')

APPROVED_COMMENT="Approved by Bot based on a high agreement score (>70%)."
REJECTED_COMMENT="Rejected by Bot - please manually review."

# gh pr comment $PR_NUMBER --edit-last --create-if-none --body "$COMMENT"
APPROVAL_SCORE=70
if ["$SCORE" -gt "$APPROVAL_SCORE" ]; then
  COMMENT_BODY=$(printf "# Pass ✅\n%s\n\n%s" "$APPROVED_COMMENT" "$COMMENT")
  gh pr review $PR_NUMBER --approve -b "$COMMENT_BODY"
else
  COMMENT_BODY=$(printf "# Rejected ❌\n%s\n\n%s" "$REJECTED_COMMENT" "$COMMENT")
  gh pr review $PR_NUMBER --request-changes -b "$COMMENT_BODY"
fi

