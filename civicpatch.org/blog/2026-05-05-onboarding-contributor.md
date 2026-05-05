---
title: "Onboarding: contributor"
date: 2026-05-05
draft: false
description: |
    Anyone with a GitHub account can review and verify AI-extracted official records on CivicPatch. Here's how.
author: "shelltr"
---

## What is a contributor?

CivicPatch scrapes elected official data from municipal websites across the US.
Before that data is published, a human reviews it. That's you.

Contributors verify scraped records, correct errors, and help keep the directory accurate.
Anyone can do it — all it takes is a GitHub account and an eye for detail.

## What you'll be reviewing

- **Name** ✦
- **Email** ✦
- **Phone** ✦
- **Profile URL** ✦
- **Role** — Mayor, Council Member, Alderman, etc.
- **Geographic designation** — ward, district, or at-large where applicable

✦ These fields are copied verbatim from the page, so what you see is exactly what the municipality published.

Role and geographic designation involve some interpretation and are worth a closer look. That said, reviewing a jurisdiction is mostly a sanity check: does the data look right at a glance, and were the correct number of people picked up? The review UI flags the most common issues automatically — missing officials, unexpected extras, role mismatches — so you're confirming those flags rather than auditing every field from scratch.

## Getting started

To get contributor access:

1. Have a [GitHub account](https://github.com/) ready
2. [Email us](mailto:michelle@civicpatch.org?subject=CivicPatch%20contributor%20access&body=Hi%2C%0A%0AI%27d%20like%20to%20be%20added%20as%20a%20CivicPatch%20contributor.%0A%0AMy%20GitHub%20username%3A%20) with information about your GitHub account.
3. [Join WG: AI Scrapers on Unified](https://unified.me/chat/!NcnsrToWrvzzzoLHWn)
    - You won't be able to create an account until we send you an invite link.

Once you've been added, **[sign in with GitHub](/api/v1/auth/github/login?redirect=/blog/onboarding-contributor)** and you'll have access to the queue and review pages.

## Your first review

The video below walks through a full review from start to finish.

<!-- Replace VIDEO_ID with the YouTube video ID once uploaded -->
<div class="video-embed">
<iframe
  width="100%"
  style="aspect-ratio: 16/9; border: none;"
  src="https://www.youtube.com/embed/VIDEO_ID"
  title="CivicPatch reviewer walkthrough"
  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
  allowfullscreen>
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