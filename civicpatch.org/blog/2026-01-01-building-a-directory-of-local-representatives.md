---
title: "CivicPatch: Building a directory of local representatives"
date: 2026-01-01
description: |
    CivicPatch is a set of civic data collection tools that combines automated web scraping and community-driven review to build and maintain a directory of representatives across US municipalities.
author: "shelltr"
---

## Problem Statement

No single authoritative source exists for who holds elected office at the municipal level. Local government contact information — mayors, council members, aldermen — is scattered across thousands of municipal websites in inconsistent formats.

Where directories do exist, the data is frequently paywalled, stale, or scoped only to the largest cities.

None of the steps required to achieve a clean data set scales without automation:

- Identifying the right pages on a given municipal site
- Extracting structured records out of unstructured content
- Resolving duplicates
- Mapping roles and districts to canonical identifiers

While building a one-off LLM scraper is straightforward for any single organization, the value of CivicPatch lies in centralization. CivicPatch makes the scrape once per jurisdiction a couple of times a year (to keep the data up to date) and publishes the results openly. This has a few benefits:

- Reduced load on municipal websites
- No duplicated engineering effort across organizations
- Data quality improves with a crowd-sourced UI
- LLM extraction costs are paid once per jurisdiction, X amount of times per year by CivicPatch, not (N organizations * X amount of times) per year

### Users this problem affects

- **Civic technology developers** building local government applications (platforms, voter tools, advocacy apps) need reliable, structured data
- **Journalists and researchers** studying local government representation, turnover, and accountability
- **Advocacy organisations** tracking which officials hold which roles across jurisdictions to target outreach need up-to-date, standardised records
- **Civic data platforms** like OpenStates need accurate upstream data to power their own transparency tools

## Project

CivicPatch uses a multi-step pipeline to collect official records for each jurisdiction.

**Google Gemini 2.5 Flash** is used on the first scrape of a jurisdiction to research who the expected elected officials are — establishing a ground truth to compare against the extracted results. This reduces the review burden on community maintainers by surfacing discrepancies automatically, rather than requiring them to verify from scratch.
- Only runs on first scrape; skipped once historical data exists for a jurisdiction
- Not swappable — tied to Google's search tool integration

**DeepSeek-V3** is used as a structured extraction model: given rendered page content, it produces typed JSON records for each official found, including name, role, geographic designation (ward, district, at-large), email, phone, and profile URL.
- Runs on every scrape
- Swappable — the evaluation framework exists specifically to validate alternative models as candidates

Results are submitted as pull requests to a public [repository](https://github.com/CivicPatch/open-data). A web-based review interface allows community maintainers to inspect, approve, or correct results before merging. A rule-based review step automatically flags discrepancies: missing officials the research step expected to find, unexpected extras, or role mismatches.

### Success Criteria

#### Speed

- Reviewing and publishing pipeline output is faster than manually researching and entering the same data:

| Method | Time per record | Sample size |
|---|---|---|
| CivicPatch review | 1m36s | 65 records |
| Manual research & entry | [TODO] | — |

#### Coverage

- **90%** of jurisdictions covered across **10 states**
- (Stretch) **90%** of jurisdictions covered across all **50 states**
- Each jurisdiction costs approximately **$[TODO]** to scrape

> Note: Extraction coverage is constrained by the identification of official municipal domains. Currently, the project has mapped and indexed official websites for 78% of Texas jurisdictions. Expanding this index is handled by the jurisdictions repository; completing that mapping is a prerequisite for automated extraction.

#### Accuracy

Pipeline output is reviewed by community maintainers before publishing, so these thresholds represent the bar for extraction quality that makes review faster than manual entry — not a requirement for perfect output.

- Official names extracted correctly at least **80%** of the time
- Roles (Mayor, Council Member, Alderman, etc.) assigned correctly at least **75%** of the time
- Geographic designations (Ward, District) correct at least **70%** of the time
- Contact information (email, phone) extracted without error at least **80%** of the time when present on the page

### Guardrails

CivicPatch only collects information that municipal governments have published on their public websites, consistent with their role as public officials. The data collected — names, roles, and official contact information — is the same information local governments are expected to publish for constituent access. Term start and end dates are collected where available but are a known limitation — accuracy is not currently guaranteed.

A human review step is built into the pipeline before data is published. Community maintainers verify AI-extracted results before they are merged into the open-data repository.

The evaluation framework is run on every prompt change to catch regressions in extraction quality.

Cost limits per pipeline run prevent runaway LLM spend.

## What we're not doing

The aim of this project is to automate the discovery and extraction of *publicly published* official contact information. As such, the project does not:

- Collect any information officials have not published in their official capacity
- Attempt to find personal contact details (personal email, home address, personal phone)
- Scrape pages that require authentication to access
- Replace the human review step with fully autonomous publishing
- (Stretch) Allow verified community contributors to submit data for jurisdictions without accessible websites

If the pipeline reaches sufficient quality and coverage across US municipalities, future work will expand to all municipalities enumerated in the CivicPatch jurisdictions repository.

[^1]: As enumerated by the [jurisdictions](https://github.com/openstates/jurisdictions) repo
