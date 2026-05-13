---
title: "How to Contribute"
date: 2026-05-05
draft: true 
description: |
    Help us verify records.
author: "shelltr"
---

## What is all this?

CivicPatch is a crowdsourced, open-source directory of local elected officials across the United States. All of our data is [publicly available on GitHub](https://github.com/CivicPatch/open-data/), with plans to provide an API for those developing civic tech-based applications.


## Help us verify records

Unlike federal and state elections, local government in the US is highly decentralized. To figure out who your elected official is, you have to go directly to your city's website. CivicPatch (with the help of organizations such as [Civic Data Tech](https://civicdatatech.github.io/)) aims to make data at the local level standardized. 

To start with, we are building a centralized registry of elected officials. Automated scrapers collect contact information directly from municipal websites, and volunteers review that data before the results make it into the dataset. 

We need your help verifying elected official records. Here are some steps to get started.

## Creating your account

Volunteer accounts require a [GitHub account](https://github.com/). User accounts are necessary for transparency — all reviews are attributed to the reviewer, which lets us audit changes and maintain confidence in the data.

To get access:

1. [Email us](mailto:michelle@civicpatch.org?subject=CivicPatch%20volunteer%20access&body=Hi%2C%0A%0AI%27d%20like%20to%20be%20added%20as%20a%20CivicPatch%20volunteer.%0A%0AMy%20GitHub%20username%3A%20) with your GitHub username.
2. [Join WG: AI Scrapers on Unified](https://unified.me/chat/!NcnsrToWrvzzzoLHWn) — you'll receive an invite link once we add you.

Once added, **[sign in with GitHub](/api/v1/auth/github/login?redirect=/blog/volunteer)** to access the queue and review pages.

## Reviewing a jurisdiction

Once signed in, click **Reviews** in the navbar to get started. Pick any state to filter reviews down to your selected state.

The review page shows the newly scraped officials alongside the existing directory entries, with a diff highlighting what changed. Your task is to confirm the right people were picked up, their roles look correct, and nothing looks obviously wrong.

The UI automatically flags common issues — missing officials, unexpected additions, role mismatches — so you're mostly confirming rather than auditing from scratch.

If a field is wrong, edit it directly in the UI before approving. Once everything looks good, approve to merge the pull request.

## What you'll be reviewing

- **Name, Email, Phone, Profile URL** — copied verbatim from the municipality's website. What you see is exactly what was published.
- **Role** — Mayor, Council Member, Alderman, etc.
- **Geographic designation** — ward, district, or at-large where applicable

## Field guidance

**Names** should match what appears on the official municipal website. If the scraped name differs from the source, correct it to match the source — not your preferred formatting.

**Profile URLs** must link to a page owned by the municipality (a council member's official bio page, not a personal site or social media profile). If the scraped URL goes to the wrong place, correct it or leave it blank rather than substituting an unofficial source.

**Roles** should use standard terminology where possible: Mayor, Council Member, Alderman, Trustee, Commissioner, etc. Use the designation on the official page if it differs.

## When something looks wrong

If the scraped data has a fixable error, edit the field directly in the review UI and then approve. Do not approve records you cannot verify.

If a jurisdiction's website is down, has no contact information, or appears to have no elected officials listed, do not approve. Leave the pull request open and file a bug using the "File a Bug" link present on every review page, and this will flag the issue to maintainers.
