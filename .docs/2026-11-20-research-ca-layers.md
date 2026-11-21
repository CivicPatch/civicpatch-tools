# California: how its local law is layered

Step 1 of the `state-offices` skill for California. Plan: `plans/2026-11-20-california-state-offices.md`.
Constitution: Article XI as leginfo shows it, read in a browser 2026-11-20 (leginfo refuses agents). Government Code:
california.public.law's copy of leginfo, marked verified 2026-11-16. Links go to leginfo.

## Ranking: constitution, general law, charter, ordinance

The constitution makes the counties, and has the Legislature provide their powers and four elected offices.
[Cal. Const. Art. XI § 1(b)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CONS&sectionNum=SEC.%201.&article=XI)
(amended 1988):

> The Legislature shall provide for county powers, an elected county sheriff, an elected district attorney, an
> elected assessor, and an elected governing body in each county.

and the cities' powers, [§ 2(a)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CONS&sectionNum=SEC.%202.&article=XI):
"The Legislature shall prescribe uniform procedure for city formation and provide for city powers."

Either may adopt a charter, which ranks as state law.
[§ 3(a)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CONS&sectionNum=SEC.%203.&article=XI)
(amended 1974):

> For its own government, a county or city may adopt a charter by majority vote of its electors voting on the
> question. The charter is effective when filed with the Secretary of State. ... A charter, amendment, revision, or
> repeal thereof shall be published in the official state statutes. ... The provisions of a charter are the law of
> the State and have the force and effect of legislative enactments.

Ordinances come last,
[§ 7](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CONS&sectionNum=SEC.%207.&article=XI):
"A county or city may make and enforce within its limits all local, police, sanitary, and other ordinances and
regulations not in conflict with general laws."

Every city is one of two classes:
[Gov. Code § 34101](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34101.),
"Cities organized under a charter shall be 'chartered cities'", and
[§ 34102](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34102.),
"Cities organized under the general law shall be 'general law cities.'" "Town" is only a name a general-law city may
take: [§ 34502](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34502.),
"the legislative body may eliminate the word 'city' from the corporate name and substitute the word 'town'". So the
Census suffix (`city`, `town`) does not tell the class.

## What a charter's silence means

### Cities: the charter is read alone

A charter city governs its municipal affairs subject only to its charter.
[§ 5(a)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CONS&sectionNum=SEC.%205.&article=XI):

> It shall be competent in any city charter to provide that the city governed thereunder may make and enforce all
> ordinances and regulations in respect to municipal affairs, subject only to restrictions and limitations provided
> in their several charters and in respect to other matters they shall be subject to general laws. City charters
> adopted pursuant to this Constitution shall supersede any existing charter, and with respect to municipal affairs
> shall supersede all laws inconsistent therewith.

Its officers are the charter's to set, § 5(b)(4):

> plenary authority is hereby granted, subject only to the restrictions of this article, to provide therein or by
> amendment thereto, the manner in which, the method by which, the times at which, and the terms for which the
> several municipal officers and employees whose compensation is paid by the city shall be elected or appointed

and the statute that sets up a city's offices covers only the other class,
[Gov. Code § 36501](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=36501.):
"The government of a general law city is vested in: (a) A city council of at least five members. (b) A city clerk.
(c) A city treasurer. ..."

So where a charter names no office, the general-law city statutes do not supply one: a charter city's offices are
its charter's (and the ordinances under it). Reading of §§ 5(a), 5(b)(4) and 36501; no section states the silent
case in words. Same answer as Oregon's cities, unlike Vermont's towns. A charter can still adopt the general law by
reference for some matter; pipeline 2 then sees that in the charter text.

### Counties: the general law fills it

A county charter displaces the general law only where it makes provision.
[§ 4(g)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CONS&sectionNum=SEC.%204.&article=XI)
(amended 1988):

> Whenever any county has framed and adopted a charter, ... the general laws adopted by the Legislature in pursuance
> of Section 1(b) of this article, shall, as to such county, be superseded by said charter as to matters for which,
> under this section it is competent to make provision in such charter, and for which provision is made therein,
> except as herein otherwise expressly provided.

"For which provision is made therein": where the charter is silent, the general law (Gov. Code Title 3) still
applies. Same answer as Vermont, Maine and New York's counties, unlike Oregon's.

### San Francisco: one charter, both

[§ 6](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CONS&sectionNum=SEC.%206.&article=XI):
"(a) A county and all cities within it may consolidate as a charter city and county as provided by statute. (b) A
charter city and county is a charter city and a charter county. Its charter city powers supersede conflicting
charter county powers." One government, carried in open-data as both "San Francisco city" and "San Francisco
County".

## Which places run under general law

- Cities: 361 general-law and 121 charter cities of 482
  ([Senate Governance and Finance Committee, City Fact Sheet, September 2016](https://sgf.senate.ca.gov/sites/sgf.senate.ca.gov/files/city_facts_2016.pdf)).
  A current count and list belongs in the cities doc.
- Counties: the counties doc counts charter and general-law counties, with a source.

## What binds a chartered place regardless of its charter

The config cannot carry these yet (`Classification` holds whole `general_law` urls only); recorded for a later field.

- Every county, charter or not, elects a sheriff, a district attorney, an assessor and its governing body (§ 1(b)),
  and a county charter must provide for them: § 4(a) "A governing body of 5 or more members, elected (1) by district
  or, (2) at large, or (3) at large, with a requirement that they reside in a district", § 4(c) "An elected
  sheriff, an elected district attorney, an elected assessor, other officers, their election or appointment".
- A charter city is "in respect to other matters ... subject to general laws" (§ 5(a)): only municipal affairs are
  its charter's.
- Term limits on council members and an elected mayor, "the city council of a general law or charter city may
  adopt" ([Gov. Code § 36502(b)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=36502.)),
  and on supervisors, "the board of supervisors of any general law or charter county"
  ([§ 25000(b)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=25000.)).

## Where a charter is published

A charter takes effect when the Secretary of State files it (§ 3(a);
[Gov. Code § 34459](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=34459.)
for cities, [§ 23713](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=23713.)
for counties), and "shall be published in the official state statutes" (§ 3(a)). A state-published index of those
filings is step 8's question.

## Answers for the config

| Classification | `lsad` | `governed_by` | Why |
|---|---|---|---|
| city | `city`, `town` | `charter_else_general_law` | a charter city's offices are its charter's (§ 5); a general-law city reads Gov. Code Title 4 (§ 36501) |
| county | `county` | `charter_or_general_law` | a county charter displaces the general law only where it provides (§ 4(g)) |
