# Prior art for a public roadmap page

Research for the CivicPatch roadmap page (a GitHub-Discussion-backed blog post).
Question: how do comparable projects present "what we're doing and what we've done",
and what can be borrowed.

## GOV.UK Design System — roadmap

<https://design-system.service.gov.uk/community/roadmap/>

The closest institutional analogue: public sector, plain language, community
contributors, work tracked in GitHub.

Section order is **Recently shipped → Working on now → Future plans**. Shipped comes
first, not last.

> "We've released GOV.UK Frontend v6.5.0, which adds the Feedback component to help
> you gather feedback from your users"

Future plans are bare objectives, no dates attached:

> "run a discovery into dark mode", "build new autocomplete components to replace
> Accessible autocomplete"

Design notes:

- Items are narrative paragraphs, not cards. No per-item status badges.
- No per-item dates anywhere. A single "Last updated 27 August 2026" at the top.
- Links out to a GitHub project board for granular detail, so the page itself never
  has to be precise.

Worth borrowing: leading with shipped work; one page-level updated date instead of
per-item dates; treating the roadmap as descriptive guidance rather than a project
management artifact.

## Keep a Changelog 1.1.0

<https://keepachangelog.com/en/1.1.0/>

The format spec, reverse-chronological, heading grammar `## [1.1.2] - 2024-09-27`
(ISO 8601 dates).

> "Changelogs are _for humans_, not machines."

Six fixed categories: Added, Changed, Deprecated, Removed, Fixed, Security. Stated
principles: every version gets an entry, like changes grouped together, versions and
sections must be linkable, latest first, release dates shown.

Worth borrowing: ISO dates, latest-first, linkable sections. Not applicable: the six
categories are release-note vocabulary, and a roadmap page is not versioned.

## Linear — changelog

<https://linear.app/changelog>

Inverts the usual hierarchy: **the date is the display heading**, large and bold
("September 3, 2026"), with the feature title in smaller type beneath it. Substantial
vertical space between entries; tighter clustering within one. Category tabs across the
top (All / Changelog / Product launches / From the team / From the community / Press)
and pagination at the bottom rather than infinite scroll.

Worth borrowing: date-as-headline. It gives chronology real typographic weight without
badges or colour, which is the opposite of the pill-and-tint approach.

## Wagtail — roadmap

<https://wagtail.org/roadmap/>

Open-source, volunteer-and-sponsor funded, so the closest match on *governance*.

Grouped by release and month — "August 2026 (v8.0)", "November 2026 (v8.1)",
"February 2027 (v8.2)", then "Future" for unscheduled work. Each entry is a title
linked to its GitHub issue, category labels (AI, DX, UX, security), and an action
button: **"Sponsor this"** or **"Contribute"**.

Completed work is not shown on the page at all — it is purely forward-looking.

Worth borrowing: every item carries a way to help. For a volunteer project the roadmap
is a recruiting surface, not only a status report. Worth rejecting: dropping history
entirely, which is most of why we want the page.

## What this suggests

1. Nobody credible uses status pills or traffic-light colour. GOV.UK and Wagtail both
   convey status by which section an item sits in.
2. Per-item dates are optional and mostly absent. GOV.UK has none; Linear makes the
   date the entire heading. The middle ground — a small mono date gutter — is the one
   position nobody takes.
3. Shipped-first (GOV.UK) is a real choice worth testing against shipped-last.
4. A contribute/help link per item is the pattern our project type actually calls for
   and none of the mockups so far have it.
