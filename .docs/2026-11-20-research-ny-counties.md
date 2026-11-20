# New York: counties

Step 1 of the `state-offices` skill, counties (57 outside New York City; open-data has 62). Layers:
`.docs/2026-11-20-research-ny-layers.md`.

Sources: County Law and MHRL on the NY Senate site; the Department of State's
[Local Government Handbook](https://dos.ny.gov/local-government-handbook-pdf), 7th edition (2018), by printed page;
NYSAC's [County Government Organization in NYS](https://www.nysac.org/media/pz3grdp0/county-organization-report-2026.pdf)
(2026), by printed page. Texts in `plans/research/new-york-state-offices/`.

## Legislative body: one per county, under several names

The County Law's board of supervisors is "The supervisors of the several cities and towns in each county"
([CNT § 150](https://www.nysenate.gov/legislation/laws/CNT/150)); a county may replace it with "an elected county
legislative body, by whatsoever name designated" ([CNT § 150-a](https://www.nysenate.gov/legislation/laws/CNT/150-A)).
Handbook p. 53: "The legislative bodies of the counties are designated by various names, including Board of
Supervisors, Board of Representatives, Board of Legislators, and County Legislature."

NYSAC 2026 (pp. 9-10) names each county's body: 15 boards of supervisors (Chenango, Columbia, Delaware, Fulton,
Hamilton, Livingston, Madison, Ontario, Saratoga, Schoharie, Seneca, Warren, Washington, Wayne, Wyoming), Otsego's
Board of Representatives, Essex "Bd. of Legislature", and a Legislature in the other 40.

A board of supervisors' members are the towns' and cities' supervisors, sitting as county officers (CNT § 150;
Art. IX § 2(c)(ii)(1)). They are elected to their town office, and the county seat comes with it.

## Executive: by charter, or an appointed administrator

The County Law "makes no provision for an independent executive or administrative authority" (handbook p. 51). A
charter "ordinarily provides for an executive or administrator, independent of the legislature" (p. 52). 23
charter counties (handbook p. 49, Table 5.3; NYSAC p. 6).

NYSAC 2026 (pp. 6, 9-10), per county:

- **Elected county executive (18, all charter)**: Albany, Broome, Chautauqua, Chemung, Dutchess, Erie, Monroe,
  Montgomery, Nassau, Oneida, Onondaga, Orange, Putnam, Rensselaer, Rockland, Suffolk, Ulster, Westchester.
- **Appointed county manager (10)**: Cayuga, Essex, Franklin, Genesee, Lewis, Niagara, Schenectady, Seneca, Steuben,
  Sullivan (Schenectady, Steuben, Sullivan by charter).
- **Appointed county administrator (23)**: Allegany, Cattaraugus, Clinton, Cortland, Fulton, Greene, Herkimer,
  Jefferson, Livingston, Madison, Ontario, Orleans, Otsego, Oswego, St. Lawrence, Saratoga, Schoharie, Schuyler,
  Tompkins, Warren, Washington, Wayne, Yates (Herkimer and Tompkins by charter; Schuyler from NYSAC p. 17, missing
  from its table).
- **Board chair and committees (6)**: Chenango, Columbia, Delaware, Hamilton, Tioga, Wyoming.

That is 57. Without a charter, an administrator is created under MHRL § 10(1)(a)(1) or CNT § 204 and acts "on
behalf of the legislature" (handbook p. 51-52): "the legislative body must retain the executive authority generally
embodied in making policy and developing the annual budget." A county manager under a charter (Schenectady, Steuben,
Sullivan) administers day to day and appoints department heads (p. 52).

Executive presence can't be told from the name; the form is per county, so no `suffixes`. The NYSAC list is the
lead for a person or a run to save each county's form.

## New York City's five counties

No county government (County Law § 2(a); MHRL § 32(3)); Table 5.2 lists them as "New York City Boroughs/Counties".
Kept in open-data without a url (plan Decisions); no form configured.

## Left out, and why

- **Sheriff, county clerk, coroner, treasurer**: elected under the County Law (handbook p. 55;
  [CNT § 400](https://www.nysenate.gov/legislation/laws/CNT/400)) but carry out tasks; the treasurer "may be
  eliminated" (p. 55). Rule 5, as decided for Maine.
- **District attorney**: a state office elected locally.
- **County judge, surrogate, family court judge** (CNT § 400): courts.
- **Chair of the legislature**: a member role (rule 2).

## Net result (counties)

| Form | Organizations | Roles | Citation |
|---|---|---|---|
| `county_executive` (18) | County Legislature; County Executive | Legislator (post), Chair (member role); County Executive (post, elected) | MHRL § 33(4)(b); NYSAC pp. 6, 10 |
| `council_manager` (33: manager or administrator) | County Legislature; County Manager / Administrator | Legislator or Supervisor (post), Chair (member role); County Manager, County Administrator (posts, appointed) | CNT § 150-a; MHRL § 10; NYSAC pp. 6, 9-10 |
| `commission` (6: chair and committees) | County Legislature | Legislator or Supervisor (post), Chair (member role) | CNT §§ 150, 150-a; NYSAC p. 9 |

Names: the organization is called "County Legislature", "Board of Supervisors", "Board of Representatives" or
"Board of Legislators" per county. Whether the config can name an organization per county, or uses one name with
the others as aliases, is a step 12 question. `governed_by: charter_or_general_law`; `general_law`: CNT §§ 150,
150-a.

Whether the `commission` form fits a board run by its chair and committees, rather than a new value, is also step 12
(and step 11 if a new value is needed).
