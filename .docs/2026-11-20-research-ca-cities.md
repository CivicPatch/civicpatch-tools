# California cities: forms and offices

Step 1 of the `state-offices` skill for California, cities and towns. Plan:
`plans/2026-11-20-california-state-offices.md`; layers: `.docs/2026-11-20-research-ca-layers.md`. Government Code
read from california.public.law's copy of leginfo (verified 2026-11-16); links go to leginfo.

## Classes and counts

Every city is chartered or general law (Gov. Code §§ 34101, 34102); "town" is a name a general-law city may take
(§ 34502), so the suffix does not tell the class, and neither does the 2026 California Roster (it prints
"Chartered City" on every entry). Only the place's own charter, or its absence, tells.

- 360 general-law and 122 charter cities; 468 (97%) council-manager, 5 mayor-council, 9 small cities where
  department heads report to the council or to single councilmembers
  ([Common Cause, California municipal key findings, 2024](https://commoncause.org/california/wp-content/uploads/2024/09/california-municipal-key-findings.pdf)).
  The same source: in 311 cities the council picks the mayor, in 170 the voters elect one; 153 elect a treasurer, 118 a
  clerk; "A few charter cities have other elected offices, for example city attorney (10) and city auditor (4)."
- open-data holds 461 `city`, 21 `town` and 1 `CDP` (below).

## General-law cities (Gov. Code Title 4)

[§ 36501](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=36501.):
"The government of a general law city is vested in: (a) A city council of at least five members. (b) A city clerk.
(c) A city treasurer. (d) A chief of police. (e) A fire chief. (f) Any subordinate officers or employees provided by
law."

**City council** (legislature), elected:
[§ 36503](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=36503.),
"all elective city offices shall be filled by the city electorate at a general municipal election"; at large, or by
or from five, seven or nine districts
([§ 34871](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34871.)).

**Mayor**, always a council member, chosen one of two ways:

- By the council:
  [§ 36801](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=36801.), the
  council shall "choose one of its number as mayor, and one of its number as mayor pro tempore." A presiding office
  the members choose: a member role, not a post (rule 2).
- By the voters, once they so decide:
  [§ 34900](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34900.), the
  council may submit "the question of whether electors shall thereafter elect a mayor and four city council members";
  [§ 34902(a)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34902.),
  "the office of mayor shall thereafter be an elective office"; and
  [§ 34903](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34903.), "The
  mayor is a member of the city council and has all of the powers and duties of a member of the city council." A post
  `elected_by_voters`, on the council.

**City manager** (executive), appointed, where an ordinance creates the office:
[§ 34851](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34851.), "An
ordinance establishing a city manager form of government may be: (a) Enacted by the legislative body"; it "shall
define the powers and duties of the city manager" ([§ 34852](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34852.));
"the legislative body shall appoint a city manager"
([§ 34855](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34855.)), who
"may appoint and dismiss the chief of police and other subordinate appointive officers and employees except the city
attorney" ([§ 34856](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34856.)).
Without such an ordinance the council runs the city itself.

So a general-law city has one shape: a council with the mayor on it, and an appointed manager where an ordinance
made one. There is no general-law mayor-council form: the mayor never sits outside the council.

**Left out**, by rule 5 (the office carries out tasks):

- City clerk, elective unless the voters make it appointive
  ([§ 36508](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=36508.),
  [§ 36510](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=36510.)):
  "shall keep an accurate record of the proceeding of the legislative body"
  ([§ 40801](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=40801.)) and
  "is the accounting officer of the city"
  ([§ 40802](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=40802.)).
- City treasurer, elective on the same terms: "shall receive and safely keep all money the treasurer receives"
  ([§ 41001](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=41001.)) and
  "shall pay out money only on warrants signed by legally designated persons"
  ([§ 41003](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=41003.)).
- Chief of police and fire chief: department heads; "The city council shall appoint the chief of police"
  ([§ 36505](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=36505.)).
- City attorney, which the council "may appoint" (§ 36505): "shall advise the city officials in all legal matters"
  ([§ 41801](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=41801.)).

## Charter cities

A charter sets the city's officers (Art. XI § 5(b)(4)); its silence does not bring in § 36501 (layers doc). The
form is told only by the charter. Council-manager is the rule; the mayor-council cities:

- **San Diego**, since 2006 (made permanent 2010).
  [Charter Art. XV](https://docs.sandiego.gov/citycharter/Article%20XV.pdf) § 260: "All executive authority, power,
  and responsibilities conferred upon the City Manager in Article V, Article VII, and Article IX shall be transferred
  to, assumed, and carried out by the Mayor"; § 265(b)(1), the Mayor is "To be the chief executive officer of the
  City"; § 270(a), "The Council shall be composed of nine councilmembers elected by district. The Council shall be
  the legislative body of the City." The mayor is not one of the nine.
- **San Francisco**. Charter § 3.100: "The Mayor shall be the chief executive officer and the official
  representative of the City and County, and shall serve full time in that capacity"
  ([San Francisco Health Service System's copy, updated November 2025](https://www.sfhss.org/resource/hss-charter-and-admin-codes-sections-updated-11-2025/download)).
  Its legislature is the Board of Supervisors, not a council (charter not read here; American Legal is browser only).
- **Fresno**. Charter § 400, as a city resolution states it: "the Mayor has the sole authority to appoint and remove
  the City Manager (Chief Administrative Officer)"
  ([Resolution 2015-201](https://www.fresno.gov/wp-content/uploads/2023/01/Reso2015201ConcerningAppointingAuthorityandResponsibility2.pdf)).
  Ballotpedia calls it a hybrid; the elected mayor is the executive and the manager answers to the mayor.
- **Los Angeles**: "Out of the top 10 cities: New York, Los Angeles, Chicago, Houston, Philadelphia, and San Diego
  have a strong mayor form of government"
  ([Ballotpedia, 2026-07-13](https://news.ballotpedia.org/2026/07/13/what-is-a-strong-mayor-government-oakland-voters-will-decide-charter-amendment-to-change-citys-form-of-government/)).
  The charter itself (American Legal, browser only) was not read.
- **Oakland**: "Currently, Oakland has a hybrid form of government" (same Ballotpedia piece), and Measure EE, "a
  strong mayor form of government", passed on 2026-11-03 with 73.7% yes
  ([KQED results](https://www.kqed.org/elections/results/alameda/measure-ee)). Its effective date is not checked.

In a mayor-council city the mayor is a post of its own, outside the council, and the manager or administrator answers
to the mayor. Other elected charter offices (city attorney, auditor, controller) advise, audit or keep accounts and
are left out by rule 5, as Oregon left out its elected auditor.

## Mountain House

A general-law city since 2024-07-01. The
[San Joaquin LAFCo recorded certificate of completion](https://sjclafco.specialdistrict.org/files/108bc53e5/Recorded+Certificate+of+Completion+-+Incorporation+of+Mountain+House.pdf):
"Incorporated City Name: City of Mountain House 3. Effective Date: July 1, 2024", and its resolution "approves name of
the new city as the City of Mountain House, which shall be incorporated as a general law city." The Census ACS
2020-2024 5-year still calls it "Mountain House CDP"; the 2025 Gazetteer calls it "Mountain House city", and
open-data's `name` now comes from the Gazetteer.

## Net result

Classification `city`: `lsad` `city`, `town`; `governed_by: charter_else_general_law` (layers doc); `general_law`
the Government Code Title 4 chapters (step 7).

| Form | Applies | Organizations and roles | Citations |
|---|---|---|---|
| `council_manager` | suffixes `city`, `town`: every general-law city, and most charter cities | `{lsad} Council` (legislature): council member, mayor, mayor pro tempore | §§ 36501(a), 36503, 36801, 34900 to 34903 |
| `mayor_council` | no suffix: saved per place for San Diego, Fresno, Los Angeles, Oakland | `{lsad} Council` (legislature): council member; Office of the Mayor (executive): mayor | San Diego Charter §§ 260, 265, 270; Fresno Charter § 400 |

The city manager or administrator (§§ 34851 to 34856) is in no form: only the council and the mayor are required
(2026-11-23, "tier 1"). A manager a scrape finds lands in the default `{lsad} Officers` as an extra, never expected.

Presiding offices the members choose (a council-chosen mayor, mayor pro tempore, council president) are member roles.
The form lists the mayor pro tempore, which § 36801 names; a "Vice Mayor" (Los Altos Hills) or a charter's "Council
President" (San Diego) parses to the level's `vice-mayor` or `president`. San Diego's "Chief Operating Officer" and
Los Angeles's "City Administrative Officer" parse to no role; one city's title each, so no state-wide alias.

Optional, not in any form, and given no role: city clerk, city treasurer, chief of police, fire chief, city
attorney, and a charter city's elected attorney, auditor or controller. Each carries out a task (above); what must be
collected is the legislative and executive body. The level's clerk, treasurer and city attorney roles parse those
titles already; the rest stay `unmatched`: collected, never an expected post.

Not configured: San Francisco's consolidated government, a special case its records leave to the suffix defaults.
Mountain House needs no `CDP` suffix: open-data's `local.py` now takes a place's name from the Census Gazetteer,
which calls it "Mountain House city", from its next run. Unread: Los Angeles's charter and Oakland's Measure EE
effective date; both only affect which places get `mayor_council` saved.
