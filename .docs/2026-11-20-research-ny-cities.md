# New York: cities

Step 1 of the `state-offices` skill, cities (62). Layers: `.docs/2026-11-20-research-ny-layers.md`.

Sources: the Department of State's [Local Government Handbook](https://dos.ny.gov/local-government-handbook-pdf),
7th edition (2018), by printed page; text in
`plans/research/new-york-state-offices/dos-local-government-handbook-7th-2018.txt`. Statutes on the NY Senate site.

## Every city by its own charter

Handbook p. 59: "Each of New York State's 62 cities is a unique governmental entity with its own special charter."
p. 61: "All cities have elected councils", and "Most cities have mayors; some mayors are elected at large by the
voters, while others are selected by the council." No general-law form (layers doc), so `governed_by: charter`.

## Four forms, told only by the charter

Handbook p. 62, the four "broad categories":

- **council-manager**: "an appointed, professional manager is the administrative head of the city, the council is
  the policymaking body and the mayor, if the position exists, is mainly a ceremonial figure".
- **strong mayor-council**: "an elective mayor is the chief executive and administrative head of the city, and the
  council is the policy making body"; "sometimes includes a professional administrator appointed by the mayor".
- **weak mayor-council**: "the mayor is mainly a ceremonial figure. The council is not only the policy making body,
  it also provides a committee form of administrative leadership."
- **commission**: "commissioners are elected by the voters to administer the individual departments of the city
  government and together form the policy making body".

Counts, p. 62: "Thirteen of the 62 cities have council-manager arrangements; three utilize the commission plan, one
of which also has a city manager. The remaining 46 cities have the mayor-council form, three of which also have a
city administrator". Per city, Table 6.1 (pp. 62-64), whose forms come from the "NYCOM 2007 Directory of City and
Village Officials", so a lead, not current:

- council-manager (13): Auburn, Batavia, Canandaigua, Corning, Elmira, Geneva, Long Beach, Newburgh, Ogdensburg,
  Peekskill, Rye, Watertown, Watervliet.
- commission (3): Mechanicville, Saratoga Springs, Sherrill (with a manager).
- mayor-council with an administrator (3): Beacon, Niagara Falls, Poughkeepsie.
- mayor-council (the other 43), New York City among them.

p. 62 also says "two cities with the council-manager form have switched to the mayor-council form", without naming
them. The form is per city, so no `suffixes`: a run's form pick or a person saves it.

## Second Class Cities Law

Handbook p. 61: it "in effect provided a uniform charter for cities of the second class, is still operative for
cities that were cities of the second class" on December 31, 1923 (SCC § 4), "until such provision is superseded".
Where it still applies it provides "a mayor, comptroller, treasurer, president of the common council and four
assessors" ([SCC § 11](https://www.nysenate.gov/legislation/laws/SCC/11)). Which cities still run on it is not
listed; a city's law read finds it, and its offices are within the forms above.

## New York City

Mayor-council with 51 council members (Table 6.1). Its five boroughs have elected presidents. Handbook p. 67: "The
five borough presidents, who are the executive officials of each borough, are also elected to four-year terms",
whose "chief responsibilities involve working with the Mayor to prepare the executive budget and propose borough
budget priorities directly to the Council, review and comment on major land use decisions and propose sites for City
facilities within their boroughs, monitor and modify the delivery of City services". They propose, review and
monitor; the mayor and council decide. Left out (rule 5; decided 2026-11-20, plan step 6a). New York City's own offices beyond mayor and council (public advocate, comptroller) are not read
yet: the city charter is the source.

## Left out, and why

- **Comptroller, treasurer, assessors** (SCC § 11 where it applies; charters elsewhere): finance officers that carry
  out tasks. Rule 5.
- **President of the common council** (SCC § 11): elected citywide in SCC cities, but presides over the council: a
  member role (rule 2), even though elected.
- **City courts**: courts.

## Net result (cities)

| Form | Organizations | Roles | Citation |
|---|---|---|---|
| `mayor_council` | City Council; Office of the Mayor | Council Member (post), Council President (member role); Mayor (post, elected); City Administrator (post, appointed) where the charter has one | handbook p. 62 |
| `council_manager` | City Council; Office of the City Manager | Council Member, Mayor (posts; the mayor sits on the council); City Manager (post, appointed) | handbook p. 62 |
| `commission` | City Council | Commissioner (post, elected), Mayor (post); City Manager where one exists (Sherrill) | handbook p. 62 |

No `suffixes` on any city form. `governed_by: charter`; `general_law` empty.
