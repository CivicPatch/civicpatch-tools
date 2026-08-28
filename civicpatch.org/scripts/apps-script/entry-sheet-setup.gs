/**
 * Builds the civicpatch data-entry spreadsheet: tabs, headers, protection.
 *
 * Standalone on purpose — a script bound to the spreadsheet is editable by everyone with Edit
 * access to it, which is every volunteer. This one opens the sheet by id and runs as whoever
 * authorized it, so there is no service account and no key anywhere.
 *
 * Idempotent: it creates what is missing and rewrites headers. It never deletes a tab, a column
 * or a row — volunteers' work lives in this file.
 *
 * HEADERS ARE A CONTRACT. They must match civicpatch.org/src/core/entry_rows.py
 * (_REQUIRED, _OPTIONAL, STATUS_COLUMNS) exactly. Matching is case-insensitive and order does
 * not matter, but the spelling does.
 */

const ROSTER_TAB = "Entry · Roster";
const JURISDICTIONS_TAB = "Entry · Jurisdictions";

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

const JURISDICTION_HEADERS = ["jurisdiction_ocdid", "ready", "rows"].concat(
  APP_OWNED,
);

// Hidden: the dropdown's source range. Sheets validation can only point at a range inside the
// same file, so the list has to live here.
const VOCAB_TAB = "Vocab · Jurisdictions";

// `/search` is a public route, so this needs no credential. 50 is its `MAX_SEARCH_LIMIT`.
// Apps Script runs on Google's network and cannot reach localhost, so this is always a
// deployed instance — override with the CIVICPATCH_URL script property.
const DEFAULT_CIVICPATCH_URL = "https://civicpatch.org";
const SEARCH_PAGE_SIZE = 50;
const SEARCH_MAX_PAGES = 200;

const HEADER_BACKGROUND = "#f3f3f3";
const APP_OWNED_BACKGROUND = "#e8eaed";

function setUpEntrySheet() {
  const id =
    PropertiesService.getScriptProperties().getProperty(
      "ENTRY_SPREADSHEET_ID",
    );
  if (!id) {
    throw new Error(
      "Set ENTRY_SPREADSHEET_ID in Project Settings → Script Properties.",
    );
  }

  const spreadsheet = SpreadsheetApp.openById(id);
  const roster = buildTab(spreadsheet, ROSTER_TAB, ROSTER_HEADERS);
  const jurisdictions = buildTab(
    spreadsheet,
    JURISDICTIONS_TAB,
    JURISDICTION_HEADERS,
  );
  makeReadyACheckbox(jurisdictions);

  const vocab = refreshJurisdictionVocab(spreadsheet, statesToOffer());
  [roster, jurisdictions].forEach(function (sheet) {
    pointOcdidAtVocab(sheet, vocab);
  });

  Logger.log("Entry sheet is set up: " + spreadsheet.getUrl());
}

/** The civicpatch instance the vocab is read from. */
function civicpatchUrl() {
  const configured =
    PropertiesService.getScriptProperties().getProperty("CIVICPATCH_URL");
  return (configured || DEFAULT_CIVICPATCH_URL).replace(/\/+$/, "");
}

/** Which states the dropdown offers, from the `ENTRY_STATES` script property (e.g. "ma,nh"). */
function statesToOffer() {
  const configured =
    PropertiesService.getScriptProperties().getProperty("ENTRY_STATES") || "ma";
  return configured
    .split(",")
    .map(function (state) {
      return state.trim().toLowerCase();
    })
    .filter(Boolean);
}

/**
 * Rewrites the hidden vocab tab from civicpatch's public jurisdiction search.
 *
 * Rewritten whole rather than merged: the list is a projection of the jurisdictions repo, and a
 * stale entry is worse than a missing one — it offers a volunteer an ocdid the import will
 * reject.
 */
function refreshJurisdictionVocab(spreadsheet, states) {
  const searchUrl = civicpatchUrl() + "/api/v1/jurisdictions/search";
  const ocdids = [];
  states.forEach(function (state) {
    for (var page = 1; page <= SEARCH_MAX_PAGES; page++) {
      const url =
        searchUrl +
        "?state=" +
        encodeURIComponent(state) +
        "&limit=" +
        SEARCH_PAGE_SIZE +
        "&page=" +
        page;
      const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
      if (response.getResponseCode() !== 200) {
        throw new Error(
          "Jurisdiction search failed (" +
            response.getResponseCode() +
            ") for " +
            state,
        );
      }
      const body = JSON.parse(response.getContentText());
      (body.data || []).forEach(function (jurisdiction) {
        ocdids.push(jurisdiction.jurisdiction_ocdid);
      });
      if (page >= body.total_pages) break;
    }
  });

  if (!ocdids.length) throw new Error("Jurisdiction search returned nothing.");
  ocdids.sort();

  const sheet =
    spreadsheet.getSheetByName(VOCAB_TAB) || spreadsheet.insertSheet(VOCAB_TAB);
  sheet.clear();
  sheet.getRange(1, 1, 1, 1).setValues([["jurisdiction_ocdid"]]);
  sheet
    .getRange(2, 1, ocdids.length, 1)
    .setValues(
      ocdids.map(function (ocdid) {
        return [ocdid];
      }),
    );
  sheet.hideSheet();

  Logger.log("Vocab · Jurisdictions: " + ocdids.length + " ocdids");
  return sheet.getRange(2, 1, ocdids.length, 1);
}

/**
 * A dropdown, and a rejecting one — an ocdid off this list is one the import will refuse, so
 * there is nothing to be gained by letting it into the sheet.
 *
 * The raw ocdid is what the cell holds, unfriendly as it looks. Sheets filters the dropdown by
 * substring and an ocdid carries its own place slug, so typing "sherborn" finds it.
 */
function pointOcdidAtVocab(sheet, vocabRange) {
  const column = headerIndex(sheet, "jurisdiction_ocdid");
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInRange(vocabRange, true)
    .setAllowInvalid(false)
    .setHelpText("Pick a jurisdiction. Type a town name to filter.")
    .build();
  sheet
    .getRange(2, column, sheet.getMaxRows() - 1, 1)
    .setDataValidation(rule);
}

function headerIndex(sheet, header) {
  const headers = sheet
    .getRange(1, 1, 1, sheet.getLastColumn())
    .getValues()[0];
  const index = headers.indexOf(header);
  if (index === -1) {
    throw new Error(sheet.getName() + " has no column " + header);
  }
  return index + 1;
}

/** Creates the tab if it is missing, writes its header row, and protects what the app owns. */
function buildTab(spreadsheet, name, headers) {
  const sheet =
    spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);

  sheet
    .getRange(1, 1, 1, headers.length)
    .setValues([headers])
    .setFontWeight("bold")
    .setBackground(HEADER_BACKGROUND);
  sheet.setFrozenRows(1);

  protectRange(sheet, sheet.getRange(1, 1, 1, headers.length), name + " header");
  headers.forEach(function (header, index) {
    if (APP_OWNED.indexOf(header) === -1) return;
    const column = sheet.getRange(1, index + 1, sheet.getMaxRows(), 1);
    column.setBackground(APP_OWNED_BACKGROUND);
    protectRange(sheet, column, name + " " + header);
  });

  return sheet;
}

/**
 * Warning-only protection, not a lock. A hard lock would need every volunteer named as an
 * exception on every range, and a new volunteer would silently lose access. This makes an
 * accidental edit ask "are you sure" — enough, because the import overwrites these columns
 * wholesale on every run anyway.
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

function makeReadyACheckbox(sheet) {
  const column = JURISDICTION_HEADERS.indexOf("ready") + 1;
  sheet
    .getRange(2, column, sheet.getMaxRows() - 1, 1)
    .insertCheckboxes();
}
