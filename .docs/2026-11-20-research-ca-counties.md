# California counties: forms and offices

Step 1 of the `state-offices` skill for California, counties. Plan: `plans/2026-11-20-california-state-offices.md`;
layers: `.docs/2026-11-20-research-ca-layers.md`. Government Code read from california.public.law's copy of leginfo
(verified 2026-11-16); links go to leginfo.

## Classes and counts

Every county is general law unless it adopted a charter (Art. XI § 3(a)); all 58 carry the suffix `county`, so the
suffix does not tell the class.

- "There are 44 general law counties and 14 charter counties"
  ([Senate Governance and Finance Committee, County Fact Sheet, 2016](https://sgf.senate.ca.gov/sites/sgf.senate.ca.gov/files/county_facts_2016.pdf)).
- Wikipedia names 15: "Alameda, Butte, El Dorado, Fresno, Los Angeles, Orange, Placer, Sacramento, San Bernardino,
  San Diego, San Francisco, San Mateo, Santa Clara, Shasta, and Tehama"
  ([List of counties in California](https://en.wikipedia.org/wiki/List_of_counties_in_California)). The counts
  disagree by one; pipeline 1 settles each county by finding its charter or not.

## General-law counties (Gov. Code Title 3)

**Board of supervisors** (legislature and executive), elected (Art. XI § 1(b), "an elected governing body in each
county"): [§ 25000(a)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=25000.),
"Each county shall have a board of supervisors consisting of five members", four-year terms. It holds both powers:
[§ 23005](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=23005.), "A county
may exercise its powers only through the board of supervisors or through agents and officers acting under authority
of the board or authority conferred by law", and
[§ 25207](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=25207.), acts
"necessary to the full discharge of the duties of the legislative authority of the county government". NACo: "The
board of supervisors also acts as the sole executive authority for each county"
([County Government Overview: California](https://ce.naco.org/app/profiles/CountyGov/CountyGov_06000.pdf)).

**Chair**, chosen by the members:
[§ 25020](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=25020.), "The
members of the board of supervisors shall elect a chairman, who shall preside at all meetings of the board." A member
role (rule 2).

**Administrative officer** (executive), appointed: a county officer by
[§ 24000(t)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=24000.), "An
administrative officer", not among the officers "to be elected by the people" (§ 24009(a)); "The Legislature or the
governing body may provide for other officers" (Art. XI § 1(b)). NACo: "Counties may appoint a chief administrator who
is responsible for the day-to-day functions of the county and for the preparation of the annual budget." Its title
varies by county (administrative officer, executive officer, administrator).

**Left out**, by rule 5. The elected officers,
[§ 24009(a)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=24009.):
"the county officers to be elected by the people are the treasurer, county clerk, auditor, sheriff, tax collector,
district attorney, recorder, assessor, public administrator, and coroner." Each carries out tasks:

- District attorney: "is the public prosecutor", who "shall initiate and conduct on behalf of the people all
  prosecutions for public offenses"
  ([§ 26500](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=26500.)).
- Sheriff: "shall preserve peace"
  ([§ 26600](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=26600.)) and
  "be the sole and exclusive authority to keep the county jail"
  ([§ 26605](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=26605.)).
- Assessor: "Annually, the assessor shall assess all the taxable property in his county"
  ([Rev. & Tax. Code § 405](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=RTC&sectionNum=405.)).
- Treasurer, tax collector, auditor, recorder, county clerk: money, accounts and records; the board may merge them
  ([§ 24300](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=24300.), e.g.
  "(g) Treasurer and tax collector", "(e) County clerk and recorder").
- Public administrator and coroner; the board "may by ordinance abolish the office of coroner and provide instead for
  the office of medical examiner, to be appointed"
  ([§ 24010](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=24010.)).

The sheriff, district attorney and assessor are elected in every county by the constitution (Art. XI § 1(b)), and any
other of these "may become an appointive office" by a vote (§ 24009(b)). Being elected is not enough (rule 5); Maine
left its sheriff out on the same reading. The superintendent of schools (§ 24000(k)) runs county education and is
left out too.

## Charter counties

A county charter "shall provide for: (a) A governing body of 5 or more members, elected ... (c) An elected sheriff,
an elected district attorney, an elected assessor, other officers, their election or appointment, compensation, terms
and removal" (Art. XI § 4), and the general law fills its silences (§ 4(g), layers doc). So a charter county has the
same board, with five or more members, and whatever executive its charter makes.

- **Los Angeles**: Measure G (passed 2024-11-05) amends the charter "to establish a directly-elected county executive
  position", with "2028: county-wide election to be held for County Executive" and "2032: expansion of the Board of
  Supervisors from five seats to nine"
  ([Wikipedia, 2024 Los Angeles County Measure G](https://en.wikipedia.org/wiki/2024_Los_Angeles_County_Measure_G)).
  Until then the board appoints its chief executive. Charter text not read.
- **San Francisco**: "a consolidated city-county government with an elected executive and an 11-member board" (NACo,
  above); the executive is the Mayor (Charter § 3.100, cities doc).
- The other charter counties: a board and an appointed executive, each per its charter, not read here; pipeline 2's
  law read sets them per county.

## Net result

Classification `county`: `lsad` `county`; `governed_by: charter_or_general_law` (layers doc); `general_law` the
Government Code Title 3 chapters (step 7).

| Form | Applies | Organizations and roles | Citations |
|---|---|---|---|
| `council_manager` | suffix `county`: every county | Board of Supervisors (legislature and executive): supervisor, chair | Art. XI §§ 1(b), 4(a); Gov. Code §§ 25000, 25020, 23005 |

The administrative officer (§ 24000(t)) is in no form: only the board is required (2026-11-23, "tier 1"). One a
scrape finds lands in the default `{lsad} Officers` as an extra, never expected; the aliases below keep its titles
parsing to `county-manager`.

`council_manager`, not `commission`: the codebase defines `commission` as "elected commissioners who together govern
and each head a department" and `council_manager` as "a council; a mayor, if there is one, sits on it; with or without
an appointed manager" (`GOVERNMENT_FORM_DESCRIPTIONS`). California's supervisors govern as one board, head no
department, and appoint an administrator.

The chair is a member role. No statute names a vice chair, so the form leaves it out; boards that name one
(Sacramento) still parse to the level's `vice-chair`.

The administrative officer's titles, as the counties' own pages write them, are aliases of `county-manager`:
"County Administrator" (the level's; Solano), "County Administrative Officer"
([Fresno](https://www.fresnocountyca.gov/Departments/County-Administrative-Office): "The County is led by the County
Administrative Officer"), "County Executive Officer" ([Riverside](https://rivco.gov/what-we-do): "reports directly to
the County Executive Officer"), "Chief Administrative Officer"
([San Diego, Chief Administrative Office](https://www.sandiegocounty.gov/content/sdc/cao.html), read through a search
result: the site refused a plain fetch's connection), "Chief Executive Officer"
([Los Angeles, 2026-05-19](https://lacounty.gov/2026/05/19/joseph-m-nicchitta-appointed-los-angeles-county-chief-executive-officer/):
"Joseph M. Nicchitta appointed Los Angeles County Chief Executive Officer"). Sacramento titles its appointed officer
"County Executive", which is the label of the level's elected `county-executive`, so no alias can take it: it parses
as an elected county executive.

Optional, not in any form, and given no role: district attorney, sheriff, assessor, treasurer, tax collector,
auditor, recorder, county clerk, public administrator, coroner, superintendent of schools. Each carries out a task
(above); what must be collected is the legislative and executive body. A title with no role stays `unmatched`:
collected, never an expected post. The level's clerk, treasurer and assessor roles parse those titles already.

Not configured: Los Angeles County's elected executive until it takes office after the 2028 election (Measure G);
San Francisco's consolidated government, a special case its records leave to the suffix defaults.
