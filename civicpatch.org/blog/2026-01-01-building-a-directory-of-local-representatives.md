---
title: "CivicPatch: Building a directory of local representatives"
date: 2026-05-05
draft: false
description: |
    CivicPatch is a set of civic data collection tools that combines automated web scraping and community-driven review to build and maintain a directory of representatives across US municipalities.
author: "shelltr"
---

## The Problem

Local government contact information for mayors, council members, and the like are scattered across thousands of municipal websites in inconsistent formats. It's not programmatically accessible to civic app developers and journalists, unless they do the upfront work of scraping everything themselves.

Where directories do exist, the data is frequently paywalled, stale, or scoped only to the largest cities.

There are a couple of challenges to solving this problem:

- Identifying the right pages on a given municipal site
- Extracting structured records out of unstructured content
- Resolving duplicates
- Mapping roles and districts to canonical identifiers

In 2026, a lot of this can be solved with a carefully worded prompt to an LLM API and a Playwright browser. Using this method, CivicPatch makes the scrape once per jurisdiction a couple of times a year (to keep the data up to date) and publishes the results to a public [repository](https://github.com/CivicPatch/open-data). This has a few benefits, assuming downstream consumers are able to use CivicPatch-derived data:

- Reduced load on municipal websites
- No duplicated engineering effort across organizations
- Data quality improves with a crowd-sourced UI
- LLM extraction costs are paid once per jurisdiction, X amount of times per year by CivicPatch, not (N organizations * X amount of times) per year

### Users this problem affects

- **Civic technology developers** building local government applications (platforms, voter tools, advocacy apps) need reliable, structured data
- **Journalists and researchers** studying local government representation, turnover, and accountability
- **Advocacy organisations** tracking which officials hold which roles across jurisdictions to target outreach
- **Civic data platforms** like OpenStates need accurate upstream data to power their own transparency tools
- **Residents of under-resourced communities** whose local representativess are less likely to appear in any structured dataset; and for whom the absence of a data standard means the tools that could reach them are never built.

> "It might require resources to maintain, which may not be feasible in rural areas with limited resources."
>
> — Martinez-Gil et al., [An Overview of Civic Engagement Tools for Rural Communities](https://pmc.ncbi.nlm.nih.gov/articles/PMC11886549/), PMC (2025), Table 5: Risks/Limitations and Mitigations in Civic Engagement Platforms for Rural Communities [civic engagement platforms, rural communities]

### Local Representatives Data and Data Standards: Some References

Civic tech has been working on this problem for over a decade — standards remain fragmented, and sustaining open, free access to representative data has been an ongoing challenge.

- In 2014, the Sunlight Foundation [launched the Open Civic Data project](https://sunlightfoundation.com/2014/11/24/help-liberate-your-towns-info-with-the-open-civic-data-project/) — a shared specification for elected official data designed to make representative information interoperable across civic tools. The Foundation [closed in 2020](https://thefulcrum.us/governance-legislation/sunlight-foundation), but the standard survived and is [still maintained today](https://open-civic-data.readthedocs.io).
- For a decade, Google's Civic Information API offered a free, structured endpoint for representative data. In April 2025, Google [shut it down](https://groups.google.com/g/google-civicinfo-api/c/9fwFn-dhktA), pointing developers toward BallotReady, Ballotpedia, and Cicero — all commercial.
- When open data infrastructure disappears and is replaced by paywalled alternatives, the tools that get built are the ones that can afford the data. As [mySociety's research found](https://research.mysociety.org/html/who-benefits/#:~:text=Those%20with%20dominant%20characteristics%20in%20affluent%20areas%20potentially%20have%20one%20aspect%20of%20their%20dominance%20reinforced), those in less affluent and more diverse communities risk having their disadvantage locked in — in part through disproportionately low engagement with civic technology tools.

**Related discussions:** [openstates/jurisdictions#54 — Develop Shared Standards for Demonstration/Review](https://github.com/openstates/jurisdictions/issues/54)

## Project

CivicPatch uses a multi-step pipeline to collect official records for each jurisdiction.

**Google Gemini 2.5 Flash** is used on the first scrape of a jurisdiction to research who the expected elected officials are — establishing a ground truth to compare against the extracted results. This reduces the review burden on community maintainers by surfacing discrepancies automatically, rather than requiring them to verify from scratch.
- Only runs on first scrape; skipped once historical data exists for a jurisdiction
- Not swappable — tied to Google's search tool integration

**DeepSeek-V3** is used as a structured extraction model: given rendered page content, it produces typed JSON records for each official found, including name, role, geographic designation (ward, district, at-large), email, phone, and profile URL.
- Runs on every scrape
- Swappable as needed

Results are submitted as pull requests to a public [repository](https://github.com/CivicPatch/open-data). A web-based review interface allows community maintainers to inspect, approve, or correct results before merging. A rule-based review step automatically flags discrepancies: missing officials the research step expected to find, unexpected extras, or role mismatches.

### Success Criteria

#### Speed

- Reviewing and publishing pipeline output is faster than manually researching and entering the same data:

| Method | Records per hour |
|---|---|
| CivicPatch review | 70 |
| Manual research & entry | 4–6 |

#### Coverage

- **80%** of jurisdictions covered across **10 states**
- (Stretch) **80%** of jurisdictions covered across all **50 states**
- Each jurisdiction costs approximately **$0.08** to scrape

> Note: Extraction coverage is constrained by the identification of official municipal domains. Currently, the project has mapped and indexed official websites for 78% of Texas jurisdictions. Expanding this index is handled by the jurisdictions repository; completing that mapping is a prerequisite for automated extraction.

#### Accuracy

Pipeline output is reviewed by community maintainers before publishing, so these thresholds represent the bar for extraction quality that makes review faster than manual entry — not a requirement for perfect output.

- Official names extracted correctly at least **80%** of the time
- Roles (Mayor, Council Member, Alderman, etc.) assigned correctly at least **75%** of the time
- Geographic designations (Ward, District) correct at least **70%** of the time
- Contact information (email, phone) extracted without error at least **80%** of the time when present on the page

### Guardrails

CivicPatch collects information that municipal governments have published on their public websites, consistent with their role as public officials. The data collected (names, roles, and contact information) is the same information local governments are expected to publish for constituent access. Term start and end dates are collected where available but are a known limitation — accuracy is not currently guaranteed.

A human review step is built into the pipeline before data is published. Community maintainers verify AI-extracted results before they are merged into the open-data repository.

The evaluation framework is run on every prompt change to catch regressions in extraction quality.

Cost limits per pipeline run prevent runaway LLM spend.

## What we're not doing

The aim of this project is to automate the discovery and extraction of *publicly published* official contact information. 

The project does not:

- Collect any information officials have not published in their official capacity
- Attempt to find personal contact details (personal email, home address, personal phone)
- Scrape pages that require authentication to access
- Replace the human review step with fully autonomous publishing
- Allow verified community contributors to submit data for jurisdictions without accessible websites

If the pipeline reaches sufficient quality and coverage across US municipalities, future work will expand to all municipalities enumerated in the CivicPatch jurisdictions repository (or the OpenStates' jurisdictions repo).
