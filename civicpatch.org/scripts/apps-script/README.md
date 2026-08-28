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
2. Paste `entry-sheet-setup.gs` in
3. **Project Settings → Script Properties**:
   - `ENTRY_SPREADSHEET_ID` = the id from the spreadsheet's URL
   - `ENTRY_STATES` = comma-separated states the dropdown offers, e.g. `ma` (defaults to `ma`)
4. Run `setUpEntrySheet`, and approve the authorization prompt on first run

Re-run it after any change to the column contract. It creates what is missing and rewrites
headers; it never deletes a tab, column or row.

## The contract

The headers must match `civicpatch.org/src/core/entry_rows.py` — `_REQUIRED`, `_OPTIONAL` and
`STATUS_COLUMNS`. Matching is case-insensitive and column order is free, but the spelling is
not. **This file is a copy of that contract and cannot be checked against it automatically**, so
a rename there is a manual edit here.

| tab | volunteer columns | app-owned |
|---|---|---|
| `Entry · Roster` | `jurisdiction_ocdid`, `name`, `label` (required); `url`, `phone`, `email`, `image`, `start_date`, `end_date` | `status`, `error`, `last_import_at` |
| `Entry · Jurisdictions` | `jurisdiction_ocdid`, `ready` | `rows`, `status`, `error`, `last_import_at` |

## The jurisdiction dropdown

`jurisdiction_ocdid` is a rejecting dropdown, sourced from a hidden `Vocab · Jurisdictions` tab
that `setUpEntrySheet` rewrites from `GET /api/v1/jurisdictions/search`. That route is public, so
this needs **no credential**.

It holds the raw ocdid, unfriendly as that looks, because that is what the importer wants and a
formula-derived column is one more thing to break. Sheets filters a dropdown by substring and an
ocdid carries its own place slug, so a volunteer types `sherborn` and finds
`ocd-jurisdiction/country:us/state:ma/county:middlesex/place:sherborn/government`.

The vocab tab is rewritten whole on every run, never merged: it is a projection of the
jurisdictions repo, and a stale entry is worse than a missing one — it offers an ocdid the
import will reject.

Re-run `setUpEntrySheet` after jurisdictions change upstream.

## Credentials

There are none in the sheet direction. The script acts as whoever authorized it, and the
jurisdiction search is public. The single secret arrives only when the sheet starts *pushing*
imports to civicpatch — an API key in this script's Script Properties, readable only by people
who can open the script, which is why it is standalone rather than bound to the spreadsheet.
