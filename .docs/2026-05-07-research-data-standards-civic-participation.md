# Research: Data Standards, Elected Official Data, and Civic Participation

**Date:** 2026-05-07
**Context:** Adding a paragraph to the CivicPatch directory blog post about why the absence of data standards for elected official contact info is a civic participation issue, not just a technical one.

---

## Sources (by relevance)

### 1. mySociety — "Who Benefits From Civic Technology?"
- **Author:** Rebecca Rumbul, mySociety / Hewlett Foundation (2015)
- **URL:** https://research.mysociety.org/publications/who-benefits-from-civic-technology
- **PDF:** https://research.mysociety.org/media/outputs/demographics-report.pdf
- **Scope:** 3,705 survey responses across UK, US, Kenya, South Africa (FixMyStreet, TheyWorkForYou, GovTrack, SeeClickFix, Mzalendo, People's Assembly)

> "This imbalance in users has the potential to reinforce disadvantage and preserve inequality. Those with dominant characteristics in affluent areas potentially have one aspect of their dominance reinforced through the maintenance of their locality, whilst those in less affluent and more diverse communities potentially have one aspect of their disadvantage locked-in, in part through disproportionally low engagement with civic technology tools."

- **Additional finding:** In UK and US, roughly 2/3 of users are male; white users are disproportionately represented relative to population share.
- **Why it's relevant:** The strongest direct statement that civic tech amplifies existing inequalities rather than correcting them. The equity consequence is named explicitly.

---

### 2. PMC — "An Overview of Civic Engagement Tools for Rural Communities"
- **URL:** https://pmc.ncbi.nlm.nih.gov/articles/PMC11886549/
- **Context:** EU Horizon Europe-funded study about gamified community collaboration platforms in rural Europe (smart villages). Not about representative data or US municipalities.

> "It might require resources to maintain, which may not be feasible in rural areas with limited resources considering the long-term sustainability."

- **Usable for:** The sustainability argument — maintaining civic data infrastructure requires ongoing resources that smaller/less-funded communities don't have. The mechanism transfers even if the context is different.
- **Risk:** A reader who follows the citation will see it's about European smart village platforms, not representative directories. Cite loosely as a general finding about civic tech sustainability in under-resourced communities, not as direct evidence about representative data.

---

### 3. mySociety — "Assessing Success in Civic Tech: Measures of Deprivation and WriteToThem"
- **Author:** Alex Parsons, mySociety (2019)
- **URL:** https://www.mysociety.org/2019/10/22/assessing-success-in-civic-tech-measures-of-deprivation-and-writetothem/

> "Using the index of multiple deprivation, more messages are sent by better off areas, with 55% of messages being sent by the less deprived half of the country, and 7% of messages coming from the most deprived decile (you would expect 10% if this were evenly divided)."

> "There is a clear linear pattern of greater employment and income in an area being associated with a greater amount of messages sent."

[Link to quote](https://www.mysociety.org/2019/10/22/assessing-success-in-civic-tech-measures-of-deprivation-and-writetothem/#:~:text=Using%20the%20index%20of%20multiple%20deprivation)

- **Why it's relevant:** Concrete statistics on usage inequality for an existing, accessible civic tool. Shows the gap even when the tool has already been built and is free to use.
- **Limitation:** Measures unequal usage of an existing tool, not the absence of tools entirely — a different problem from the one CivicPatch addresses.

---

### 4. Google — "Notice of Turndown of the Representatives API"
- **URL:** https://groups.google.com/g/google-civicinfo-api/c/9fwFn-dhktA
- **Date:** April 2025

> "There are alternate providers who are able to serve authoritative representation data directly to developers."

- **What happened:** Google shut down `representativeInfoByAddress` and `representativeInfoByDivision` in April 2025, pointing developers to BallotReady, Ballotpedia, Cicero, and 5Calls — all commercial. The Elections and Divisions APIs remain active.
- **Why it's relevant:** A concrete, recent illustration of what happens without an open standard — a free public resource disappears and is replaced by paywalled alternatives. Google's migration path uses OCD-IDs (`divisionsByAddress`), confirming the standard is still active infrastructure.

---

### 5. mySociety — "Analysis of Users and Usage for TheyWorkForYou.com"
- **Author:** Tobias Escher, Oxford Internet Institute / mySociety (2011)
- **URL:** https://research.mysociety.org/publications/impact-of-uk-parliamentary-sites
- **Note:** Full findings are in the PDF download — quotes not extractable from the landing page.
- **Key finding (from abstract):** 60% of TheyWorkForYou visitors had never previously looked up who their representative was, suggesting the information access barrier is real and that lowering it drives first-time civic engagement.
- **Why it's relevant:** Establishes that the access barrier is real and that removing it produces new civic engagement — not just more of the same.

---

### 6. mySociety — "Civic Tech Cities"
- **URL:** https://research.mysociety.org/html/civic-tech-cities/
- **Scope:** Case studies of civic tech in Austin, Chicago, Oakland, Washington DC, and Seattle.
- **Key finding:** Study selection was implicitly biased toward well-resourced cities — only tools "operational for at least one year" were included, which filtered out smaller municipalities. The research identifies "digitally skilled employees" and budgetary capacity as significant determinants of civic tech success.
- **Why it's relevant:** Indirect signal — even the academic literature on civic tech defaults to major metros, reflecting where the tools exist.
- **Limitation:** Does not systematically compare outcomes across city sizes; five cases, all major metros.

---

### 7. Sunlight Foundation — "Help Liberate Your Town's Info with the Open Civic Data Project!"
- **Author:** Paul Tagliamonte, Sunlight Foundation (2014)
- **URL:** https://sunlightfoundation.com/2014/11/24/help-liberate-your-towns-info-with-the-open-civic-data-project/
- **Note:** The Sunlight Foundation closed in September 2020. The site is a static archive. The Open Civic Data standard lives on at [github.com/opencivicdata](https://github.com/opencivicdata); docs at [open-civic-data.readthedocs.io](https://open-civic-data.readthedocs.io).

> "Or being able to enter your zip code on a website to find out who your representatives are — from your town to state capitol to Congress — and seeing what bills they're voting on and how you can get in touch to have your voice be heard?"

[Link to quote](https://sunlightfoundation.com/2014/11/24/help-liberate-your-towns-info-with-the-open-civic-data-project/#:~:text=Or%20being%20able%20to%20enter%20your%20zip%20code%20on%20a%20website)

- **Why it's relevant:** Historical context — the original vision for what open civic data standards were meant to enable. Useful as a "this was the promise; here's where we are now" framing.

---

## Sources Ruled Out

- **Knight Columbia — "Voter Data, Democratic Inequality..."** — about citizen voter *history* data used by campaigns, not about elected official data. Not relevant.
- **NDI — Open Election Data Initiative** — about election administration data, not representative directories.
- **Pew — "Civic Engagement Strongly Tied to Local News Habits"** — too broad; not specific to official contact data access.
