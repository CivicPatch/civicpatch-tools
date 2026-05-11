---
title: "How to Contribute"
date: 2026-05-05
draft: false
description: |
    Verify your elected officials.
author: "shelltr"
---

## We Need Your Help!

Volunteers verify scraped records, correct errors, and help keep the directory accurate.

## What you'll be reviewing

- **Name** ✦
- **Email** ✦
- **Phone** ✦
- **Profile URL** ✦
- **Role** — Mayor, Council Member, Alderman, etc.
- **Geographic designation** — ward, district, or at-large where applicable

✦ These fields are copied verbatim from the page, so what you see is exactly what the municipality published.

## See also

- [Democracy Club — Volunteer](https://candidates.democracyclub.org.uk/volunteer/) — a similar volunteer-driven project in the UK that verifies candidate data for elections

## Getting started

To get volunteer access:

1. Have a [GitHub account](https://github.com/) ready
2. [Email us](mailto:michelle@civicpatch.org?subject=CivicPatch%20volunteer%20access&body=Hi%2C%0A%0AI%27d%20like%20to%20be%20added%20as%20a%20CivicPatch%20volunteer.%0A%0AMy%20GitHub%20username%3A%20) with information about your GitHub account.
3. [Join WG: AI Scrapers on Unified](https://unified.me/chat/!NcnsrToWrvzzzoLHWn)
    - You won't be able to create an account until we send you an invite link.

Once you've been added, **[sign in with GitHub](/api/v1/auth/github/login?redirect=/blog/onboarding-volunteer)** and you'll have access to the queue and review pages.

## The review

The review page shows the scraped data and a diff from what was previously scraped for the jurisdiction. 

Check that the right people were picked up, their roles look correct, and nothing looks obviously off. 

The UI flags common issues — missing officials, unexpected extras, role mismatches — so you're mostly confirming rather than auditing from scratch. Edit any field directly in the UI if something needs fixing, then approve to merge.

<zoom-image src="/blog/images/onboarding_review_page.webp" alt="The CivicPatch review page showing a list of scraped officials alongside the existing directory entries"></zoom-image>

## The queue

The queue lists jurisdictions with pending scraped data waiting for review. Pick any one to open the page for that jurisdiction, or close/publish the pull request if you want to do bulk reviews.

<zoom-image src="/blog/images/onboarding_queue_page.webp" alt="The CivicPatch queue page listing jurisdictions with pending scraped data"></zoom-image>

## Walkthrough

The video below walks through a full review from start to finish.

<div class="video-embed">
<iframe
  width="100%"
  style="aspect-ratio: 16/9; border: none;"
  src="https://drive.google.com/file/d/1WVNhRTLN7LTeJPjNfOFJWCDwiyexlePD/preview"
  allow="autoplay">
</iframe>
</div>

<!-- After the video, add a timestamped outline so readers can jump to the part they need:

**In this video:**

- 0:00 — Opening the review queue
- 0:00 — Reading the diff panel
- 0:00 — What the automatic flags mean (missing, extra, role mismatch)
- 0:00 — Editing a record directly in the UI
- 0:00 — Approving and merging
- 0:00 — What happens after merge
-->

<!--
## Common questions

Cover the most likely stumbling blocks:
     - "What if the scraped data is wrong?" → edit in the review UI before approving
     - "What if the jurisdiction has no website?" → flag it, don't approve
     - "How often do new PRs come in?" → scrape cadence


## Questions?

[TODO: community channel, email, GitHub discussions — wherever people should go]
-->
