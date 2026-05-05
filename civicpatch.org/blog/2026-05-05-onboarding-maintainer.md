---
title: "Onboarding: maintainer"
date: 2026-05-05
draft: true
description: |
    Maintainers keep the CivicPatch pipeline running — triaging failed runs, managing issues, and configuring role mappings. Here's what the role involves and how to get access.
author: "shelltr"
---

## What is a maintainer?

Maintainers take ownership of the data for a specific state or region. They are invested in the 
overall quality and completeness of a state's dataset over time.

If you have a reason to care about a particular state — you live there, research it, or
just want to see it done well — this role is for you!

## What maintainers can do

- **Issues page** — a dedicated view of jurisdictions flagged for issues like dead URLs or
  unrecognized roles. For unrecoverable errors, you will want to fix these before we
  re-run scrapes. Failure to do so will result in those jurisdictions being skipped over
  until the errors are resolved/fixed.
- **Role configuration** — map raw scraped role strings (e.g. "Alderperson",
  "Trustee") to canonical roles at the state or locality level.
- **Pipeline runs** — trigger a new scrape for a jurisdiction, view what ran and
  what failed, and resume a paused run.

## Getting access

To get maintainer access:

1. Have a [GitHub account](https://github.com/) ready
2. [Email us](mailto:michelle@civicpatch.org?subject=CivicPatch%20maintainer%20access&body=Hi%2C%0A%0AI%27d%20like%20to%20maintain%20data%20for%20a%20specific%20state%20on%20CivicPatch.%0A%0AMy%20GitHub%20username%3A%20%0AState%20I%27d%20like%20to%20maintain%3A%20) with your GitHub username and the state you'd like to maintain.
3. [Join WG: AI Scrapers on Unified](https://unified.me/chat/!NcnsrToWrvzzzoLHWn)
    - You won't be able to create an account until we send you an invite link.

Once you've been added, **[sign in with GitHub](/api/v1/auth/github/login?redirect=/blog/onboarding-maintainer)** and you'll have access to the maintainer tools.

## Walkthrough

The video below walks through the maintainer tools from start to finish.

<!-- Replace VIDEO_ID with the YouTube video ID once uploaded -->
<div class="video-embed">
<iframe
  width="100%"
  style="aspect-ratio: 16/9; border: none;"
  src="https://www.youtube.com/embed/VIDEO_ID"
  title="CivicPatch maintainer walkthrough"
  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
  allowfullscreen>
</iframe>
</div>

<!-- Timestamp outline once recorded:

**In this video:**

- 0:00 — The issues page
- 0:00 — Triggering a pipeline run
- 0:00 — Reading run context and errors
- 0:00 — Role configuration
-->

## The queue page

<!-- What it shows: pending PRs across all jurisdictions, filterable by state.
     How maintainers should use it differently from contributors — focus on their state.
     Screenshot guidance: queue filtered to a single state with a few open PRs. -->

[TODO]

## The issues page

<!-- What it shows: jurisdictions flagged for dead URLs or unrecognized roles.
     What to do with each:
     - Dead URL → find the new official site, update the jurisdiction record
     - Unrecognized role → map it to a canonical role in the role config
     Screenshot guidance: issues page with at least one dead-URL and one role flag visible. -->

[TODO]
<!--
## Triggering and managing pipeline runs

<!-- How to trigger a run for a specific state or jurisdiction.
     What the run context view shows (which steps ran, how long, what failed).
     How to resume a paused run vs when to let it fail.
     Screenshot guidance: run context view mid-run, and an error state.

[TODO]

## Role configuration

What role configs are: mappings from raw scraped role strings to canonical roles.
     State-level vs locality-level overrides.
     How to add a new mapping when the issues page flags an unrecognized role.
     Screenshot guidance: role config editor with an example mapping.

[TODO]
## Common questions

- "When should I trigger a run vs wait for the scheduled one?" → scrape cadence, stale data
     - "What if a run keeps failing?" → escalate to admins, don't resolve/cancel (that's admin only)
     - "Can I edit role configs globally?" → no, that's admin only; state/locality level only

[TODO]

## Questions?

[TODO: community channel, email, GitHub discussions — wherever people should go]
-->