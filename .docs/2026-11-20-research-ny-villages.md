# New York: villages

Step 1 of the `state-offices` skill, villages (531). Layers: `.docs/2026-11-20-research-ny-layers.md`.

Sources: Village Law on the NY Senate site; the Department of State's
[Local Government Handbook](https://dos.ny.gov/local-government-handbook-pdf), 7th edition (2018), by printed page;
text in `plans/research/new-york-state-offices/dos-local-government-handbook-7th-2018.txt`.

## One form: the board of trustees with a mayor

"Every village shall have the following officers: a. a mayor; b. four trustees, except that the board of trustees
of a village may change the number of trustees", and "c. a treasurer; d. a clerk."
"The mayor, trustees and village justices shall be elective officers. All other officers shall be appointed by the
mayor, subject to the approval of the board of trustees." "The mayor and the trustees of a village shall constitute
the board of trustees thereof." ([VIL § 3-301](https://www.nysenate.gov/legislation/laws/VIL/3-301))

The board legislates: it "shall have management of village property and finances, may take all measures and do all
acts, by local law" ([VIL § 4-412](https://www.nysenate.gov/legislation/laws/VIL/4-412)). The mayor presides and
runs the government day to day: "To preside at the meetings of the board of trustees", "to appoint all department
and non-elected officers and employees subject to the approval of the board of trustees", "to exercise supervision
over the conduct of the police and other subordinate officers of the village"
([VIL § 4-400](https://www.nysenate.gov/legislation/laws/VIL/4-400)). Handbook p. 85: "The chief executive officer
of most villages in New York State is the mayor", who "may vote on all questions coming before that body."

So the mayor is a post on the Board of Trustees, elected, like Vermont's and Michigan's `village_board`.

**Deputy mayor**: "to appoint one of the trustees as deputy mayor" (VIL § 4-400): a member role, rule 2.

## Village manager or administrator: by local law

Handbook p. 85: "The position of village manager is created by a local law, which fixes the powers of the office
and the term of the incumbent." "Fifty five villages in New York State had an administrator or manager in 2005;
they are listed in Table 8.2" (p. 86, from the 2005 NYCOM directory, so dated). No Village Law section creates the
office; it rests on MHRL § 10(1)(ii)(a)(1). An appointed post (rule 3).

## Charter villages

Handbook p. 83: "The Village Law governs the incorporation of new villages and the organization of most existing
villages. The 12 remaining charter villages are subject to this law only where it does not conflict with their
respective charters." The handbook doesn't name them. For these 12 the general law fills the charter's silence,
which `general_law` with the village's own law read covers; no separate class.

## Left out, and why

- **Clerk, treasurer**: appointed by the mayor (VIL § 3-301(3)); carry out tasks. Rule 5.
- **Assessors** and "such other officers ... as the board of trustees shall determine" (VIL § 3-301(2)): optional,
  appointed. Rule 5.
- **Village justices**: courts.

## Net result (villages)

| Form | Organization | Roles | Citation |
|---|---|---|---|
| `village_board` | Board of Trustees (legislature) | Mayor (post, elected; presides), Trustee (post, elected); Deputy Mayor (member role) | VIL §§ 3-301, 4-400, 4-412 |
| | Office of the Village Manager (executive), only where a local law made one | Village Manager / Administrator (post, appointed) | handbook p. 85; MHRL § 10(1)(ii)(a)(1) |

`suffixes`: `village`.
