# Maine: where each place's code is published

Step 1.4 of the `state-offices` skill. Layers: [2026-11-20-research-me-layers.md](2026-11-20-research-me-layers.md).

## Sources, 2026-11-20

- **ICC Code Solutions**, https://www.icccodesolutions.org/text-library/ (`div.state ME`): 39 entries, all
  eCode360.
- **Municode**, https://api.municode.com/Clients/stateAbbr?stateAbbr=ME, opened in a browser and saved:
  `plans/research/maine-state-offices/municode-me-2026-11-20.json`, 12 clients. The JSON carries no code url; the
  url below is built from `ClientName` (`library.municode.com/me/<name>`) and is not checked.

Matched to `data_source/me/{local,counties}/jurisdictions.yml` with pipeline 1's `charter_title_matches`
(`pipelines/src/runners/pipeline01_governing_law_collector/finders/state_index.py`): ICC titles "{lsad} of {place}"
and "{place} {lsad}", Municode "{place}". All 51 matched one place each: none ambiguous, none unmatched. No county
is listed in either.

## What a fetch allowed

| Host | Places | Plain fetch | Agent web fetch | Charter checked |
|---|---|---|---|---|
| eCode360 | 39 | 403 | 403 | none |
| Municode | 12 | not tried (refuses agents) | not tried | none |

eCode360 let a plain fetch through for Oregon on 2026-11-06; for Maine on 2026-11-20 it refused both. Not worked
around. 430 of Maine's 481 places are in neither directory.

## Places

| Place | Host | Code url | Charter in the code |
|---|---|---|---|
| Alfred town | ecode360.com | https://ecode360.com/AL1317 | not checked (eCode360 403) |
| Auburn city | municode | https://library.municode.com/me/auburn | not checked (Municode refuses agents) |
| Augusta city | ecode360.com | https://ecode360.com/AU3534 | not checked (eCode360 403) |
| Bangor city | ecode360.com | https://ecode360.com/BA1684 | not checked (eCode360 403) |
| Bar Harbor town | ecode360.com | https://ecode360.com/BA1953 | not checked (eCode360 403) |
| Belfast city | ecode360.com | https://ecode360.com/BE3520 | not checked (eCode360 403) |
| Bethel town | ecode360.com | https://ecode360.com/BE2000 | not checked (eCode360 403) |
| Biddeford city | ecode360.com | https://ecode360.com/BI3074 | not checked (eCode360 403) |
| Boothbay Harbor town | ecode360.com | https://ecode360.com/BO1465 | not checked (eCode360 403) |
| Brewer city | municode | https://library.municode.com/me/brewer | not checked (Municode refuses agents) |
| Brunswick town | municode | https://library.municode.com/me/brunswick | not checked (Municode refuses agents) |
| Bucksport town | ecode360.com | https://ecode360.com/BU6754 | not checked (eCode360 403) |
| Camden town | ecode360.com | https://ecode360.com/CA4299 | not checked (eCode360 403) |
| Casco town | municode | https://library.municode.com/me/casco | not checked (Municode refuses agents) |
| Cumberland town | ecode360.com | https://ecode360.com/CU3016 | not checked (eCode360 403) |
| Durham town | ecode360.com | https://ecode360.com/DU6850 | not checked (eCode360 403) |
| Eliot town | municode | https://library.municode.com/me/eliot | not checked (Municode refuses agents) |
| Freeport town | municode | https://library.municode.com/me/freeport | not checked (Municode refuses agents) |
| Frye Island town | ecode360.com | https://ecode360.com/FR6691 | not checked (eCode360 403) |
| Gardiner city | ecode360.com | https://ecode360.com/GA6894 | not checked (eCode360 403) |
| Gorham town | ecode360.com | https://ecode360.com/GO6630 | not checked (eCode360 403) |
| Hollis town | municode | https://library.municode.com/me/hollis | not checked (Municode refuses agents) |
| Islesboro town | ecode360.com | https://ecode360.com/IS3006 | not checked (eCode360 403) |
| Kennebunkport town | ecode360.com | https://ecode360.com/KE3910 | not checked (eCode360 403) |
| Kittery town | ecode360.com | https://ecode360.com/KI3028 | not checked (eCode360 403) |
| Lisbon town | municode | https://library.municode.com/me/lisbon | not checked (Municode refuses agents) |
| Livermore town | municode | https://library.municode.com/me/livermore | not checked (Municode refuses agents) |
| Madison town | ecode360.com | https://ecode360.com/MA2740 | not checked (eCode360 403) |
| Mechanic Falls town | ecode360.com | https://ecode360.com/ME4300 | not checked (eCode360 403) |
| Ogunquit town | ecode360.com | https://ecode360.com/OG3870 | not checked (eCode360 403) |
| Old Orchard Beach town | municode | https://library.municode.com/me/old_orchard_beach | not checked (Municode refuses agents) |
| Old Town city | ecode360.com | https://ecode360.com/OL4196 | not checked (eCode360 403) |
| Orono town | municode | https://library.municode.com/me/orono | not checked (Municode refuses agents) |
| Raymond town | ecode360.com | https://ecode360.com/RA4290 | not checked (eCode360 403) |
| Rumford town | ecode360.com | https://ecode360.com/RU3995 | not checked (eCode360 403) |
| Saco city | ecode360.com | https://ecode360.com/SA1647 | not checked (eCode360 403) |
| Sanford city | ecode360.com | https://ecode360.com/SA2111 | not checked (eCode360 403) |
| Shapleigh town | ecode360.com | https://ecode360.com/SH1616 | not checked (eCode360 403) |
| South Berwick town | ecode360.com | https://ecode360.com/SO1284 | not checked (eCode360 403) |
| Standish town | ecode360.com | https://ecode360.com/ST1289 | not checked (eCode360 403) |
| Topsham town | ecode360.com | https://ecode360.com/TO1615 | not checked (eCode360 403) |
| Wales town | ecode360.com | https://ecode360.com/WA6808 | not checked (eCode360 403) |
| Waterville city | ecode360.com | https://ecode360.com/WA3904 | not checked (eCode360 403) |
| Wayne town | ecode360.com | https://ecode360.com/WA6819 | not checked (eCode360 403) |
| Wells town | ecode360.com | https://ecode360.com/WE1006 | not checked (eCode360 403) |
| Westbrook city | ecode360.com | https://ecode360.com/WE3873 | not checked (eCode360 403) |
| Windham town | ecode360.com | https://ecode360.com/WI1257 | not checked (eCode360 403) |
| Winslow town | ecode360.com | https://ecode360.com/WI3839 | not checked (eCode360 403) |
| Winthrop town | ecode360.com | https://ecode360.com/WI6923 | not checked (eCode360 403) |
| Wiscasset town | municode | https://library.municode.com/me/wiscasset | not checked (Municode refuses agents) |
| York town | ecode360.com | https://ecode360.com/YO6991 | not checked (eCode360 403) |

## Use

These are the urls a person uses for `source_blocked` and `governing_law_not_found` issues, and a lead for the
planned code-directory finder. A charter check per place needs a person with a browser, or the ground-truth step
(step 6) reading the charters of the places it picks.
