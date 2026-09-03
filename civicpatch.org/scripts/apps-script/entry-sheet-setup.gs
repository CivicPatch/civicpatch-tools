/**
 * Builds the civicpatch data-entry spreadsheet: tabs, headers, protection, the dropdown.
 *
 * Structure only. The backend owns every app-owned tab's *contents* — `Live[Jurisdictions]`
 * and the per-state `Live[People][XX]`, `Live[Memberships][XX]`, `Live[Posts][XX]` — and
 * creates them itself, because only it knows which states exist. This script no longer reads
 * civicpatch at all, so it needs no API key and cannot hit the six-minute execution limit.
 *
 * Standalone on purpose — a script bound to the spreadsheet is editable by everyone with Edit
 * access to it, which is every volunteer.
 *
 * `setUpEntrySheet` is idempotent and re-runnable. `resetLiveTabs` is the one destructive
 * function and is meant to be run once, when the sheet carries tabs from an older shape.
 *
 * HEADERS ARE A CONTRACT. They must match civicpatch.org/src/core/entry_rows.py
 * (_REQUIRED, _OPTIONAL, STATUS_COLUMNS). Case-insensitive, order-free, spelling exact.
 */

// Not a secret — access is Drive sharing, not knowing this string.
const ENTRY_SPREADSHEET_ID = "16tGgkC40p3OGp7kRNlkqsA4V86Y5JdbEPQLK5cBkuIc";

const ROSTER_TAB = "Entry[Roster]";

// Written by the import, never by a volunteer.
const APP_OWNED = ["status", "error", "last_import_at"];

const ROSTER_HEADERS = [
  "jurisdiction_ocdid", // required
  "name", // required
  "label", // required
  "url",
  "phone",
  "email",
  "image",
  "start_date",
  "end_date",
].concat(APP_OWNED);

// The dropdown's source. Created empty here so the validation range is valid on a fresh sheet;
// the backend fills it on its next sync and owns every row.
const LIVE_JURISDICTIONS_TAB = "Live[Jurisdictions]";
const JURISDICTION_COLUMN = "jurisdiction_ocdid";

const HEADER_BACKGROUND = "#f3f3f3";
const APP_OWNED_BACKGROUND = "#e8eaed";

function setUpEntrySheet() {
  const spreadsheet = SpreadsheetApp.openById(ENTRY_SPREADSHEET_ID);
  const roster = buildTab(spreadsheet, ROSTER_TAB, ROSTER_HEADERS);
  const jurisdictions = buildTab(spreadsheet, LIVE_JURISDICTIONS_TAB, [
    JURISDICTION_COLUMN,
  ]);
  pointOcdidAtJurisdictions(roster, jurisdictions);

  Logger.log("Entry sheet is set up: " + spreadsheet.getUrl());
  Logger.log(
    "Now run POST /api/admin/sheet_sync/jurisdictions to fill the dropdown.",
  );
}

// Every app-owned tab starts with this. `Entry[` is the volunteer's and is never touched.
const LIVE_PREFIX = "Live[";

/**
 * Deletes every app-owned tab, so the backend rebuilds them from scratch.
 *
 * Separate from `setUpEntrySheet`, which never deletes anything — this is the one destructive
 * function here and it should be a deliberate choice, not a side effect of setup.
 *
 * Use it when the sheet carries tabs from an older shape: the one-state design left an
 * unsuffixed `Live[People]` and `Live[Posts]` behind, and those sit next to the per-state ones
 * looking equally official with different numbers in them.
 *
 * `Entry[Roster]` is never deleted — that is volunteer typing, and nothing here can give it back.
 */
function resetLiveTabs() {
  const spreadsheet = SpreadsheetApp.openById(ENTRY_SPREADSHEET_ID);
  const removed = [];
  spreadsheet.getSheets().forEach(function (sheet) {
    const name = sheet.getName();
    if (name.indexOf(LIVE_PREFIX) !== 0) return;
    spreadsheet.deleteSheet(sheet);
    removed.push(name);
  });

  Logger.log(
    removed.length
      ? "Deleted " + removed.length + ": " + removed.join(", ")
      : "Nothing to delete.",
  );
  Logger.log("Now run setUpEntrySheet, then the two sheet_sync endpoints.");
}

/**
 * A rejecting dropdown over every jurisdiction, every state — which is what lets one
 * Entry[Roster] take any state's rows.
 *
 * The range is open-ended (`A2:A`), not `(2, 1, lastRow - 1, 1)`. The backend rewrites that tab
 * and the row count moves, so a bounded range would silently stop covering the newest entries.
 *
 * The cell holds the raw ocdid because that is what the importer wants, and Sheets filters a
 * dropdown by substring — so typing `sherborn` still finds it.
 *
 * Measured 2026-09-03 at 9,496 entries: 1-2s to filter as you type. Usable. But that is
 * roughly a quarter of national coverage, so ~40k plausibly means 4-8s, which is not. If it
 * gets there, swap the rule for a formula, which renders no list at all:
 *
 *   .requireFormulaSatisfied(
 *     "=COUNTIF('" + LIVE_JURISDICTIONS_TAB + "'!$A$2:$A, A2)>0")
 *
 * That keeps typo rejection and drops the range-size coupling, at the cost of autocomplete —
 * which is the only thing making a raw ocdid typeable. Measure before trading it away.
 */
function pointOcdidAtJurisdictions(sheet, jurisdictions) {
  const column = headerIndex(sheet, JURISDICTION_COLUMN);
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInRange(jurisdictions.getRange("A2:A"), true)
    .setAllowInvalid(false)
    .setHelpText("Pick a jurisdiction. Type a town name to filter.")
    .build();
  sheet.getRange(2, column, sheet.getMaxRows() - 1, 1).setDataValidation(rule);
}

function headerIndex(sheet, header) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const index = headers.indexOf(header);
  if (index === -1) {
    throw new Error(sheet.getName() + " has no column " + header);
  }
  return index + 1;
}

/** Creates the tab if missing, writes its header row, and protects what the app owns. */
function buildTab(spreadsheet, name, headers) {
  const sheet =
    spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);

  sheet
    .getRange(1, 1, 1, headers.length)
    .setValues([headers])
    .setFontWeight("bold")
    .setBackground(HEADER_BACKGROUND);
  sheet.setFrozenRows(1);
  formatAsText(sheet, headers.length);

  protectRange(
    sheet,
    sheet.getRange(1, 1, 1, headers.length),
    name + " header",
  );
  headers.forEach(function (header, index) {
    if (APP_OWNED.indexOf(header) === -1) return;
    const column = sheet.getRange(1, index + 1, sheet.getMaxRows(), 1);
    column.setBackground(APP_OWNED_BACKGROUND);
    protectRange(sheet, column, name + " " + header);
  });

  return sheet;
}

/**
 * Warning-only, not a lock. A hard lock needs every volunteer named as an exception on every
 * range, and a new volunteer would silently lose access.
 */
function protectRange(sheet, range, description) {
  sheet
    .getProtections(SpreadsheetApp.ProtectionType.RANGE)
    .filter(function (existing) {
      return existing.getDescription() === description;
    })
    .forEach(function (existing) {
      existing.remove();
    });

  range.protect().setDescription(description).setWarningOnly(true);
}

/**
 * Plain text, so Sheets stores what was typed instead of interpreting it.
 *
 * Three things this prevents, all of which have bitten: a phone like "+1 360 555 0177" parsed
 * as a formula and rendered #ERROR!, a date typed as 2024-01-01 stored as the serial 45292, and
 * anything starting with "=" becoming a live formula.
 */
function formatAsText(sheet, columns) {
  const rows = Math.max(sheet.getMaxRows() - 1, 1);
  sheet.getRange(2, 1, rows, columns).setNumberFormat("@");
}
