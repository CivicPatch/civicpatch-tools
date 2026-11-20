# New York: towns

Step 1 of the `state-offices` skill, towns (933). Layers: `.docs/2026-11-20-research-ny-layers.md`.

Sources: Town Law on the NY Senate site; the Department of State's
[Local Government Handbook](https://dos.ny.gov/local-government-handbook-pdf), 7th edition (November 16, 2018),
cited by its printed page. Its extracted text is kept in
`plans/research/new-york-state-offices/dos-local-government-handbook-7th-2018.txt`.

## One form, two statutory classes

Every town has a town board of the supervisor and council members:
"In every town the supervisor and the town council members shall constitute the town board" and "shall be vested
with all the powers of such a town" ([TWN § 60](https://www.nysenate.gov/legislation/laws/TWN/60)). The handbook
(p. 72): "The legislative body of the town is the town board."

The class changes the number and the elected officers, not the form
([TWN § 20](https://www.nysenate.gov/legislation/laws/TWN/20)):

- First class: "a supervisor, four town council members"; elective are "The supervisor, town counsel members, town
  clerk, town justices," and "town superintendent of highways and receiver of taxes and assessments".
- Second class: "a supervisor, two justices of the peace, two town council members"; elected are "The supervisor,
  justices of the peace, town council members, town clerk, town superintendent of highways," and "assessors and
  collector".

Which class: 10,000 or more is first class, with exceptions by county (TWN § 10); a town may also opt up (handbook
p. 71). The handbook (p. 72) on the difference today: "To all intents and purposes, all towns, regardless of their
statutory classification, possess roughly equivalent legal powers." Class can't be told from the name and doesn't
change the organizations, so it is not configured.

**Suburban towns** (TWN art. 3-A) are first-class towns that opted in
([TWN § 50-a](https://www.nysenate.gov/legislation/laws/TWN/50-A)); "The supervisor shall be the chief executive
officer of a suburban town" ([TWN § 52](https://www.nysenate.gov/legislation/laws/TWN/52)). The handbook (p. 73):
"Although designated as 'chief executive officer', the Suburban Town supervisor has no major new executive
powers." Same organizations.

## The supervisor: a board member, not a separate executive

Handbook p. 73: "The Town Law does not provide for a separate executive branch of town government", and "the
supervisor is part of the legislative branch and acts as a member and presiding officer of the town board", "having
no additional tie-breaking or veto power." So the supervisor is a post on the Town Board, elected, not an office
of its own.

## Town manager: a few towns, by local law

"Any town may, by local law, establish the office of town manager"
([TWN § 58](https://www.nysenate.gov/legislation/laws/TWN/58), art. 3-B). Handbook p. 73: "Since 1998, the Towns of
Collins, Erwin, Mount Kisco, Putnam and Southampton have been operating under a town manager form of government."
An appointed post, kept in the data and filtered from the elected view (rule 3). A town's own local law is the
only way to tell.

Any town may also create a town executive by local law superseding the Town Law (handbook p. 73: "Offices such as
town executive and town manager may be established"; MHRL § 10(1)(ii)(d)(3)). None was counted.

## Coterminous town-villages

Handbook p. 82: five villages (Green Island, East Rochester, Scarsdale, Harrison, Mount Kisco) "are coterminous
with towns of the same name", and "the governing
body of one unit of the coterminous government may serve as the governing body of the other unit (i.e., the mayor
serves as town supervisor and trustees serve as members of the town board)." Open-data has both a town and a
village record for each; the same people will show in both. Not configured specially.

## Left out, and why

- **Town clerk, receiver of taxes and assessments, collector, assessors**: elected in some classes (TWN § 20), but
  they carry out tasks; a town "may ... create and/or abolish elective as well as appointive offices" by local law
  (handbook p. 73, the 1976 change). Rule 5, as decided for Maine's clerk and treasurer (Maine plan step 2a).
- **Town superintendent of highways**: elected (TWN § 20) but runs a department under the board's budget and may be
  made appointive or abolished (TWN § 20(1)(k), (6)(b)). Rule 5 (decided 2026-11-20, plan step 6a).
- **Town justices**: courts.

## Net result (towns)

| Form | Organization | Roles | Citation |
|---|---|---|---|
| `township_board` | Town Board (legislature) | Supervisor (post, elected; presides), Council Member (post, elected) | TWN §§ 20, 60; handbook p. 72-73 |
| | Office of the Town Manager (executive), only where a local law made one | Town Manager (post, appointed) | TWN § 58 |

`suffixes`: `town`. Every town has the same form, so the suffix decides it. The town manager is configured as a
role the law read can find, not as a second form (5 towns).
