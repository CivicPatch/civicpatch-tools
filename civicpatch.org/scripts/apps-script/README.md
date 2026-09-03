# Apps Script for the data-entry spreadsheet

`entry-sheet-setup.gs` builds the sheet's tabs, headers, protections and the jurisdiction
dropdown. **Structure only** — every app-owned tab's contents come from the backend.

## What owns what

| tab | contents written by |
|---|---|
| `Entry[Roster]` | volunteers; the importer stamps `status` / `error` / `last_import_at` |
| `Live[Jurisdictions]` | backend — every active jurisdiction, all states, the dropdown source |
| `Live[People][XX]` | backend — one row per person, everyone we hold, seated or not |
| `Live[Memberships][XX]` | backend — one row per membership, closed ones included |
| `Live[Posts][XX]` | backend — one row per seat, whether or not anyone holds it |

The backend creates the per-state tabs itself, sizes their grids and protects them, because only
it knows which states exist. This script never touches them.

**Three tabs, three grains** — count the rows and you get people, memberships, seats. They differ:
Washington holds 1,616 people and 1,612 memberships. A curator scanning for a near-miss *name*
wants the people tab; "who holds what, and who used to" is the memberships tab; a seat nobody has
ever filled appears only on the posts tab.

## Why Apps Script rather than the app

Building tabs, protections and data validation is spreadsheet structure, and the Sheets API's
`batchUpdate` is a clumsy way to express it. Apps Script also runs as the person who authorized
it, so there is no key here to store or leak.

## Why standalone rather than bound to the sheet

A container-bound script (Extensions → Apps Script from inside the spreadsheet) is editable by
anyone with Edit access to that spreadsheet — every volunteer. A standalone script opens the
spreadsheet by id and is invisible to them.

## Setup

1. [script.google.com](https://script.google.com) → **New project**, named `civicpatch entry sheet`
2. Paste `entry-sheet-setup.gs` in
3. Set `ENTRY_SPREADSHEET_ID` at the top of the file to your spreadsheet
4. Run `setUpEntrySheet`, approving the authorization prompt on first run
5. Share the spreadsheet with the backend's service account as an **Editor**
6. `POST /api/admin/sheet_sync/jurisdictions` to fill the dropdown, then
   `POST /api/admin/sheet_sync/rosters` to fill the state tabs

**No script properties and no API key.** Nothing here reads civicpatch.

Re-run `setUpEntrySheet` after any change to the roster column contract. It creates what is
missing and rewrites headers; it never deletes a tab, column or row.

**`resetLiveTabs` is the one destructive function**, and it is deliberately not part of setup.
It deletes every `Live[...]` tab so the backend rebuilds them, which is what you want on a sheet
carrying tabs from an older shape — the one-state design left an unsuffixed `Live[People]` and
`Live[Posts]` behind. `Entry[Roster]` is never deleted: that is volunteer typing, and nothing
here can give it back.

## One sheet, every state

There is no `ENTRY_STATE`. `Entry[Roster]` takes rows for any jurisdiction in any state, and the
importer groups them by jurisdiction on the way in — it never cared what state a row was in. The
old `refuseForeignStateRows` guard existed only because the dropdown was scoped to one state.

That is also why `Live[Jurisdictions]` is one flat tab rather than one per state: Sheets data
validation can point at exactly one contiguous range.

## The jurisdiction dropdown

`jurisdiction_ocdid` is a rejecting dropdown sourced from `Live[Jurisdictions]!A2:A` —
open-ended, because the backend rewrites that tab and a bounded range would stop covering new
rows.

It holds the raw ocdid, unfriendly as that looks, because that is what the importer wants and a
formula-derived column is one more thing to break. Sheets filters a dropdown by substring and an
ocdid carries its own place slug, so a volunteer types `sherborn` and finds
`ocd-jurisdiction/country:us/state:ma/county:middlesex/place:sherborn/government`.

A friendly name column is not an option now that the sheet covers every state: there is a
Springfield in about thirty of them, so a name alone is ambiguous.

**Dropdown speed, measured 2026-09-03**: 1-2s to filter as you type, at 9,496 entries. Usable.

That is about a quarter of national coverage, so ~40k entries plausibly means 4-8s, which is
not. If it gets there, `pointOcdidAtJurisdictions` carries a commented
`requireFormulaSatisfied` alternative that renders no list — it keeps typo rejection and loses
autocomplete, which is the only thing making a raw ocdid typeable.

## The contract

Headers must match `civicpatch.org/src/core/entry_rows.py` — `_REQUIRED`, `_OPTIONAL` and
`STATUS_COLUMNS`. Matching is case-insensitive and column order is free, but the spelling is
not. **This file is a copy of that contract and cannot be checked against it automatically**, so
a rename there is a manual edit here.

| tab | volunteer columns | app-owned |
|---|---|---|
| `Entry[Roster]` | `jurisdiction_ocdid`, `name`, `label` (required); `url`, `phone`, `email`, `image`, `start_date`, `end_date` | `status`, `error`, `last_import_at` |
