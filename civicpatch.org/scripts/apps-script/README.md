# Apps Script for the data-entry spreadsheet

`entry-sheet-setup.gs` builds the sheet's tabs, headers and protections.

## Why Apps Script rather than the app

Reading and writing the sheet from civicpatch needs a Google service account and a long-lived
private key — the credential type Google itself recommends migrating away from. Apps Script runs
as the person who authorized it, so there is no key to store, rotate, or leak, and the grant is
revocable at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## Why standalone rather than bound to the sheet

A container-bound script (Extensions → Apps Script from inside the spreadsheet) is editable by
anyone with Edit access to that spreadsheet — every volunteer. Anything it holds, they can read.
A standalone script opens the spreadsheet by id and is invisible to them.

## Setup

1. [script.google.com](https://script.google.com) → **New project**, named `civicpatch entry sheet`
2. Paste `entry-sheet-setup.gs` in, then **+ → Script** and paste `live-tabs.gs` as a second file
3. **Project Settings → Script Properties** — only if you are not pointing at prod:
   - `CIVICPATCH_URL` = e.g. a tailscale funnel to your dev instance

`ENTRY_SPREADSHEET_ID` and `ENTRY_STATE` are constants at the top of the file, not properties:
one sheet per state, so which sheet this script drives is a property of the script, not of a
run. The id is not a secret — access is Drive sharing, not knowing the string.
4. Run `setUpEntrySheet`, and approve the authorization prompt on first run

Run `checkConfig` instead when something fails — it prints the resolved properties and the
reachable state list without touching the spreadsheet, which separates "the properties are
wrong" from "the spreadsheet is wrong".

Re-run it after any change to the column contract. It creates what is missing and rewrites
headers; it never deletes a tab, column or row.

## The contract

The headers must match `civicpatch.org/src/core/entry_rows.py` — `_REQUIRED`, `_OPTIONAL` and
`STATUS_COLUMNS`. Matching is case-insensitive and column order is free, but the spelling is
not. **This file is a copy of that contract and cannot be checked against it automatically**, so
a rename there is a manual edit here.

| tab | volunteer columns | app-owned |
|---|---|---|
| `Entry[Roster]` | `jurisdiction_ocdid`, `name`, `label` (required); `url`, `phone`, `email`, `image`, `start_date`, `end_date` | `status`, `error`, `last_import_at` |
| `Entry[Jurisdictions]` | `jurisdiction_ocdid`, `ready` | `rows`, `status`, `error`, `last_import_at` |
| `Live[Jurisdictions]` | — | `jurisdiction_ocdid`, `name`, `level` (the whole state) |
| `Live[People]` | — | `jurisdiction_ocdid`, `name`, `labels`, `image` |
| `Live[Posts]` | — | `jurisdiction_ocdid`, `organization`, `label`, `role_id`, `division_ocdid` |

## The Live tabs

App-owned reference, rewritten whole on every run — they are projections of civicpatch, and a
stale row is worse than a missing one because it shows a curator a seat or a person who is no
longer there.

Their job is stopping near-misses: someone who can see Sherborn already has a
"Select Board Member" will not type "Selectboard Member" and mint a second post for the same
seat.

`Live[People]` and `Live[Posts]` cover **only the jurisdictions named on the worklist**, not
the whole state — reference for forty towns is useful, and for three hundred and fifty it is one
request per town for data nobody reads. Both reads are public routes, so still no credential.

## One state at a time

The sheet is scoped to a single state, set by `ENTRY_STATE` at the top of `entry-sheet-setup.gs`
(`ENTRY_LEVELS` next to it narrows to `local` or `counties`; empty offers both). They are
constants rather than script properties — configuration nobody was going to change, and one more
thing to get wrong.

To switch states, finish or clear the entry rows first. `setUpEntrySheet` refuses to run while
`Entry[Roster]` or `Entry[Jurisdictions]` hold rows for another state: re-pointing the dropdown
under them would leave every one of those rows failing validation, and this script never deletes
what a volunteer typed, so it cannot tidy up after itself.

## The jurisdiction dropdown

`jurisdiction_ocdid` is a rejecting dropdown, sourced from column A of `Live[Jurisdictions]`,
which `setUpEntrySheet` rewrites from `GET /api/v1/jurisdictions/search`. That route is public,
so this needs **no credential**. 

It holds the raw ocdid, unfriendly as that looks, because that is what the importer wants and a
formula-derived column is one more thing to break. Sheets filters a dropdown by substring and an
ocdid carries its own place slug, so a volunteer types `sherborn` and finds
`ocd-jurisdiction/country:us/state:ma/county:middlesex/place:sherborn/government`.

Re-run `setUpEntrySheet` after jurisdictions change upstream.

## Credentials

There are none in the sheet direction. The script acts as whoever authorized it, and the
jurisdiction search is public. The single secret arrives only when the sheet starts *pushing*
imports to civicpatch — an API key in this script's Script Properties, readable only by people
who can open the script, which is why it is standalone rather than bound to the spreadsheet.
