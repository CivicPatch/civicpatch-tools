# Maine: how its local law is layered

Step 1 of the `state-offices` skill for Maine. Plan: `plans/2026-11-20-maine-state-offices.md`.
Statute pages are the Revisor's text (page footer: data extracted 10/05/2026).

## Ranking: constitution, general law, charter, ordinance

The constitution grants charter home rule, bounded by the constitution and general law.
[Me. Const. Art. VIII, Pt. 2, § 1](https://lldc.mainelegislature.org/Open/Const/Versions/MeConst_2024_Amd.pdf):

> The inhabitants of any municipality shall have the power to alter and amend their charters on all matters, not
> prohibited by Constitution or general law, which are local and municipal in character. The Legislature shall
> prescribe the procedure by which the municipality may so act.

Title 30-A, chapter 111 is that procedure.
[§ 2101](https://legislature.maine.gov/statutes/30-A/title30-Asec2101.html): "to implement the home rule powers
granted to municipalities by the Constitution of Maine, Article VIII, Part Second". A charter may hold nothing the
general law prohibits: the municipal attorney must certify, before it goes to the voters, that it "does not contain
any provision prohibited by the United States Constitution, the Constitution of Maine or the general laws"
([§ 2103(5)(D)(4)](https://legislature.maine.gov/statutes/30-A/title30-Asec2103.html); same for amendments,
[§ 2104(5)(B)](https://legislature.maine.gov/statutes/30-A/title30-Asec2104.html)).

Ordinances sit under all three.
[§ 3001](https://legislature.maine.gov/statutes/30-A/title30-Asec3001.html): a municipality may "exercise any power
or function granted to the municipality by the Constitution of Maine, general law or charter", where that power is
"not denied either expressly or by clear implication", and the Legislature is not taken to deny a power "unless the
municipal ordinance in question would frustrate the purpose of any state law" (§ 3001(3)).

Private and special laws (how Maine's older cities were chartered) stand until a charter revision replaces them:
[§ 2107](https://legislature.maine.gov/statutes/30-A/title30-Asec2107.html), "Private and special laws applying to a
municipality remain in effect until repealed or amended by a charter revision".

## What a charter's silence means: the general law fills it

The general law on officers is written as a default a charter may override, so where a charter says nothing, the
statute applies. Same answer as Vermont, unlike Oregon.

- [§ 2526](https://legislature.maine.gov/statutes/30-A/title30-Asec2526.html), choice of town officials, opens:
  "Unless otherwise provided by charter, the following provisions apply".
- [§ 2601(1)](https://legislature.maine.gov/statutes/30-A/title30-Asec2601.html), appointments: "Except where
  specifically provided by law, charter or ordinance", the municipal officers appoint all officials required by
  general law, charter or ordinance.
- [§ 2001(10)](https://legislature.maine.gov/statutes/30-A/title30-Asec2001.html) defines the municipal officers
  for both kinds of place: "The members of the select board or councillors of a town"; "The mayor and aldermen or
  councillors of a city".

So `governed_by` for a chartered place reads the charter with the general law behind it.

## Which places run under general law

No statute requires a charter; a charter is adopted or revised by vote
([§ 2102](https://legislature.maine.gov/statutes/30-A/title30-Asec2102.html)). Title 30-A provides two charterless
town forms:

- **Town meeting and select board**, the default: the town meeting is the legislative body
  ([§ 2001(9)(A)](https://legislature.maine.gov/statutes/30-A/title30-Asec2001.html)); the town elects a select
  board of 3, 5 or 7 ([§ 2526(4)(A)](https://legislature.maine.gov/statutes/30-A/title30-Asec2526.html)).
- **Town manager plan**, adopted by town meeting vote: an elected select board and "an appointed town manager"
  ([§ 2631](https://legislature.maine.gov/statutes/30-A/title30-Asec2631.html),
  [§ 2632](https://legislature.maine.gov/statutes/30-A/title30-Asec2632.html)).

Neither form can be told from a town's name; only the town's own records say whether it adopted the plan or a
charter.

- **Cities** have a city council as legislative body (§ 2001(9)(B)). No general-law city form was found in Title 30-A;
  each city is set up by its charter (private and special law or a home-rule charter). Step 2 confirms this per city.
- **Plantations** (28) run under town law "as far as applicable, except when specifically provided otherwise"
  ([§ 7006](https://legislature.maine.gov/statutes/30-A/title30-Asec7006.html)); their 3 elected assessors "are
  considered the members of the select board of the plantation"
  ([§ 7007](https://legislature.maine.gov/statutes/30-A/title30-Asec7007.html),
  [§ 7001(4)](https://legislature.maine.gov/statutes/30-A/title30-Asec7001.html)).
- **Counties** run under Title 30-A, chapter 1 (an elected board of commissioners,
  [§ 61](https://legislature.maine.gov/statutes/30-A/title30-Asec61.html)) unless their voters adopt a charter under
  chapter 11 ([§ 1301](https://legislature.maine.gov/statutes/30-A/title30-Asec1301.html)), which "may determine the
  officers of the county".

## `governed_by` per classification, and the urls each reads

Every Title 30-A section is its own page; no chapter is one page. Each section's text is far under
`WHOLE_TEXT_CHARS` (`pipelines/src/runners/pipeline02_organizations_collector/sections.py`) on its own and summed, so
every url is read whole: no `section_format` needed. Text sizes measured 2026-11-20 are in
`plans/research/maine-state-offices/` notes, not here.

| Class | lsad | `governed_by` | Why |
|---|---|---|---|
| town | town | `charter_or_general_law` | § 2526, § 2601(1): "unless otherwise provided by charter" |
| city | city | `charter_or_general_law` | every city has a charter (MMA); § 2001(10)(B) and § 2601(1) fill its silence |
| plantation | plantation | `general_law` | no home rule, so no charter (MMA); town law applies "as far as applicable" (§ 7006) |
| county | county | `charter_or_general_law` | [§ 1352(1)](https://legislature.maine.gov/statutes/30-A/title30-Asec1352.html): the general laws on commissioners (§§ 61 to 82), treasurer, budget and registers "do not apply if the charter provides for that function" |

`general_law` urls:

- **town**: [§ 2001](https://legislature.maine.gov/statutes/30-A/title30-Asec2001.html),
  [§ 2526](https://legislature.maine.gov/statutes/30-A/title30-Asec2526.html),
  [§ 2601](https://legislature.maine.gov/statutes/30-A/title30-Asec2601.html),
  [§ 2631](https://legislature.maine.gov/statutes/30-A/title30-Asec2631.html),
  [§ 2632](https://legislature.maine.gov/statutes/30-A/title30-Asec2632.html),
  [§ 2635](https://legislature.maine.gov/statutes/30-A/title30-Asec2635.html),
  [§ 2636](https://legislature.maine.gov/statutes/30-A/title30-Asec2636.html). § 2524 (moderator) is left out: the
  moderator is not collected.
- **city**: § 2001, § 2601.
- **plantation**: [§ 7001](https://legislature.maine.gov/statutes/30-A/title30-Asec7001.html),
  [§ 7006](https://legislature.maine.gov/statutes/30-A/title30-Asec7006.html),
  [§ 7007](https://legislature.maine.gov/statutes/30-A/title30-Asec7007.html), § 2526.
- **county**: [§ 61](https://legislature.maine.gov/statutes/30-A/title30-Asec61.html),
  [§ 61-A](https://legislature.maine.gov/statutes/30-A/title30-Asec61-A.html),
  [§ 67](https://legislature.maine.gov/statutes/30-A/title30-Asec67.html),
  [§ 82](https://legislature.maine.gov/statutes/30-A/title30-Asec82.html).

### Law that binds a chartered place regardless

The config cannot carry these yet; recorded for a later field.

- A charter may contain nothing "prohibited by ... the general laws" (§ 2103(5)(D)(4), § 2104(5)(B)) and only
  matters "local and municipal in character" (Me. Const. Art. VIII, Pt. 2, § 1).
- § 2001(10): who the municipal officers are, in a town and in a city.
- A county charter that abolishes the commissioners, treasurer or register of deeds "must designate" who does their
  statutory duties ([§ 1352(2)](https://legislature.maine.gov/statutes/30-A/title30-Asec1352.html)).

## Places in open-data

`data_source/me/local/jurisdictions.yml`, 2026-11-20: 430 towns, 23 cities, 28 plantations (481).
43 places have no `url`. 16 counties.

Data error found: Lewiston city's `url` and `wiki_url` point at Mechanic Falls.

## Open for step 2

- How many towns run town meeting and select board, how many the town manager plan, how many a charter (a town
  council). No state list found yet.
- § 61 says each county board is "a chairman and 2 other persons", § 61-A gives York 5, but
  [§ 67](https://legislature.maine.gov/statutes/30-A/title30-Asec67.html) draws 5 districts in Cumberland, Franklin
  and Somerset and 7 in Androscoggin. The session law (PL 2021, c. 552) or a county-specific section has to settle it.
- Which counties have adopted a chapter 11 charter.
