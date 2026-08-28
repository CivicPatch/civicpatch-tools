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

// Jurisdictions is three things at once: the reference list, the roster dropdown's source
// (validation can only point inside the same file), and the worklist that `ready` ticks.
const LIVE_JURISDICTIONS_TAB = "Live[Jurisdictions]";
const LIVE_PEOPLE_TAB = "Live[People]";
const LIVE_POSTS_TAB = "Live[Posts]";

// `ready` is the one cell a volunteer owns on the Jurisdictions tab.
const READY = "ready";
const LIVE_JURISDICTION_HEADERS = [
  "jurisdiction_ocdid",
  "name",
  READY,
  "url",
  "population",
  "level",
  "rows",
].concat(APP_OWNED);

// One row per person-membership, and the two projected labels rather than raw sighting text:
// `post_label` is what the seat is called, `membership_label` what this person's turn in it is.
const LIVE_PEOPLE_HEADERS = [
  "jurisdiction_ocdid",
  "name",
  "post_label",
  "membership_label",
  "urls",
  "phones",
  "emails",
  "image",
  "start_date",
  "end_date",
  "other_names",
  "source_urls",
];
const LIVE_POST_HEADERS = [
  "jurisdiction_ocdid",
  "organization",
  "post_label",
  "role_id",
  "division_ocdid",
];

// Past this the per-jurisdiction reference fetches run into the execution limit.
const MAX_WORKLIST = 200;

// `/search` is a public route, so this needs no credential. 50 is its `MAX_SEARCH_LIMIT`.
// Apps Script runs on Google's network and cannot reach localhost, so this is always a
// deployed instance — override with the CIVICPATCH_URL script property.
const DEFAULT_CIVICPATCH_URL = "https://civicpatch.org";
const SEARCH_PAGE_SIZE = 50;

// The dev Washington sheet. Not a secret — access is Drive sharing, not knowing this id.
const ENTRY_SPREADSHEET_ID = "16tGgkC40p3OGp7kRNlkqsA4V86Y5JdbEPQLK5cBkuIc";

// One state per spreadsheet. Set this to the state this sheet is for; the guard below refuses to
// run if the entry tabs already hold another state's rows.
const ENTRY_STATE = "wa";
// "" offers local and counties, which is what the API does by default; "local" narrows it.
const ENTRY_LEVELS = "";

/**
 * Every script property this uses, and why. A standalone script cannot prompt — Browser and
 * SpreadsheetApp.getUi() both need a bound document — so the next best thing is naming all the
 * missing ones at once instead of failing on the first.
 */
const PROPERTIES = [
  {
    name: "CIVICPATCH_URL",
    required: false,
    about: "civicpatch instance to read from; defaults to " + DEFAULT_CIVICPATCH_URL,
  },
];

const HEADER_BACKGROUND = "#f3f3f3";
const APP_OWNED_BACKGROUND = "#e8eaed";

function setUpEntrySheet() {
  requireProperties();
  const spreadsheet = SpreadsheetApp.openById(ENTRY_SPREADSHEET_ID);
  const roster = buildTab(spreadsheet, ROSTER_TAB, ROSTER_HEADERS);
  refuseForeignStateRows([roster]);

  const jurisdictions = refreshLiveJurisdictions(spreadsheet);
  pointOcdidAtJurisdictions(
    roster,
    jurisdictions.getRange(2, 1, jurisdictions.getLastRow() - 1, 1),
  );
  refreshLiveTabs(spreadsheet, jurisdictions);

  Logger.log("Entry sheet is set up: " + spreadsheet.getUrl());
}

/** Names every missing required property in one message, rather than one run per property. */
function requireProperties() {
  const properties = PropertiesService.getScriptProperties();
  const missing = PROPERTIES.filter(function (property) {
    return property.required && !properties.getProperty(property.name);
  });
  if (!missing.length) return;

  throw new Error(
    "Set these in Project Settings → Script Properties:\n" +
      missing
        .map(function (property) {
          return "  " + property.name + " — " + property.about;
        })
        .join("\n"),
  );
}

/** Prints the resolved config without touching the spreadsheet. Run this when setup fails. */
function checkConfig() {
  const properties = PropertiesService.getScriptProperties();
  Logger.log("ENTRY_SPREADSHEET_ID: " + ENTRY_SPREADSHEET_ID + "  (constant)");
  Logger.log("ENTRY_STATE: " + ENTRY_STATE + "  (constant)");
  Logger.log("ENTRY_LEVELS: " + (ENTRY_LEVELS || "(both)") + "  (constant)");
  PROPERTIES.forEach(function (property) {
    const value = properties.getProperty(property.name);
    Logger.log(
      property.name +
        ": " +
        (value || "(unset)") +
        (property.required ? "  [required]" : "  [optional — " + property.about + "]"),
    );
  });

  const statesUrl = civicpatchUrl() + "/api/v1/jurisdictions/states";
  const response = UrlFetchApp.fetch(statesUrl, { muteHttpExceptions: true });
  Logger.log(statesUrl + " -> HTTP " + response.getResponseCode());
  Logger.log(response.getContentText().slice(0, 500));
}

function civicpatchUrl() {
  const configured =
    PropertiesService.getScriptProperties().getProperty("CIVICPATCH_URL");
  return (configured || DEFAULT_CIVICPATCH_URL).replace(/\/+$/, "");
}

/** Independent requests sent together — round trips dominate. A bad one is null, not a throw. */
function fetchAllJson(urls) {
  const requests = urls.map(function (url) {
    return { url: url, muteHttpExceptions: true };
  });
  return UrlFetchApp.fetchAll(requests).map(function (response) {
    if (response.getResponseCode() !== 200) return null;
    try {
      return JSON.parse(response.getContentText());
    } catch (e) {
      return null;
    }
  });
}

/**
 * Stops before rewriting anything if the Entry tabs hold another state's rows: re-pointing the
 * dropdown under them would leave every one failing validation, and this cannot tidy up after it.
 */
function refuseForeignStateRows(sheets) {
  const foreign = {};
  sheets.forEach(function (sheet) {
    ocdidsIn(sheet).forEach(function (ocdid) {
      const match = /\/state:([a-z]{2})\//.exec(ocdid);
      const state = match ? match[1] : "?";
      if (state !== ENTRY_STATE) foreign[state] = (foreign[state] || 0) + 1;
    });
  });

  const states = Object.keys(foreign);
  if (!states.length) return;
  throw new Error(
    "The entry tabs still hold rows for " +
      states
        .map(function (state) {
          return foreign[state] + " x " + state;
        })
        .join(", ") +
      ', but ENTRY_STATE is "' +
      ENTRY_STATE +
      '". Finish or clear those rows before switching states.',
  );
}

/** Two batched rounds: page one gives the count, the rest go in a single fetchAll. */
function refreshLiveJurisdictions(spreadsheet) {
  const first = fetchAllJson([searchPageUrl(1)])[0];
  if (!first || !(first.data || []).length) {
    throw new Error(
      'No jurisdictions for state "' +
        ENTRY_STATE +
        '" at ' +
        civicpatchUrl() +
        ". Check it against " +
        civicpatchUrl() +
        "/api/v1/jurisdictions/states",
    );
  }

  const rows = [];
  collectJurisdictions(rows, first);

  const remaining = [];
  for (var page = 2; page <= first.total_pages; page++) {
    remaining.push(searchPageUrl(page));
  }
  fetchAllJson(remaining).forEach(function (body) {
    if (body) collectJurisdictions(rows, body);
  });

  rows.sort(function (a, b) {
    return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0;
  });
  Logger.log(
    LIVE_JURISDICTIONS_TAB + ": " + rows.length + " " + ENTRY_STATE + " jurisdictions",
  );

  return writeJurisdictions(spreadsheet, rows);
}

/**
 * Writes the jurisdiction list, keeping whatever is ticked `ready`.
 *
 * The list is a projection of civicpatch and gets rewritten whole, but `ready` is the one cell a
 * volunteer owns on this tab. It is restored by ocdid, so a town keeps its tick even if the list
 * reorders or grows underneath it.
 */
function writeJurisdictions(spreadsheet, rows) {
  const sheet =
    spreadsheet.getSheetByName(LIVE_JURISDICTIONS_TAB) ||
    spreadsheet.insertSheet(LIVE_JURISDICTIONS_TAB);
  const wasReady = readyByOcdid(sheet);
  const readyColumn = LIVE_JURISDICTION_HEADERS.indexOf(READY);

  const values = rows.map(function (row) {
    const filled = LIVE_JURISDICTION_HEADERS.map(function (_, index) {
      return index < row.length ? row[index] : "";
    });
    filled[readyColumn] = wasReady[row[0]] === true;
    return filled;
  });

  sheet.clear();
  sheet
    .getRange(1, 1, 1, LIVE_JURISDICTION_HEADERS.length)
    .setValues([LIVE_JURISDICTION_HEADERS])
    .setFontWeight("bold")
    .setBackground(HEADER_BACKGROUND);
  sheet.setFrozenRows(1);
  if (values.length) {
    sheet
      .getRange(2, 1, values.length, LIVE_JURISDICTION_HEADERS.length)
      .setValues(values);
  }
  sheet
    .getRange(2, readyColumn + 1, Math.max(sheet.getMaxRows() - 1, 1), 1)
    .insertCheckboxes();

  // Everything but `ready` is app-owned, so protect around it rather than the whole tab.
  LIVE_JURISDICTION_HEADERS.forEach(function (header, index) {
    if (header === READY) return;
    const column = sheet.getRange(1, index + 1, sheet.getMaxRows(), 1);
    column.setBackground(APP_OWNED_BACKGROUND);
    protectRange(sheet, column, LIVE_JURISDICTIONS_TAB + " " + header);
  });

  return sheet;
}

/** What is ticked today, keyed by ocdid, so a rewrite does not lose it. */
function readyByOcdid(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return {};
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const ocdidColumn = headers.indexOf("jurisdiction_ocdid");
  const readyColumn = headers.indexOf(READY);
  if (ocdidColumn === -1 || readyColumn === -1) return {};

  const ticked = {};
  sheet
    .getRange(2, 1, lastRow - 1, sheet.getLastColumn())
    .getValues()
    .forEach(function (row) {
      const ocdid = String(row[ocdidColumn] || "").trim();
      if (ocdid && row[readyColumn] === true) ticked[ocdid] = true;
    });
  return ticked;
}

function searchPageUrl(page) {
  return (
    civicpatchUrl() +
    "/api/v1/jurisdictions/search?state=" +
    encodeURIComponent(ENTRY_STATE) +
    "&limit=" +
    SEARCH_PAGE_SIZE +
    "&page=" +
    page +
    (ENTRY_LEVELS ? "&level=" + encodeURIComponent(ENTRY_LEVELS) : "")
  );
}

function collectJurisdictions(rows, body) {
  (body.data || []).forEach(function (jurisdiction) {
    // Positions match LIVE_JURISDICTION_HEADERS up to `level`; `ready` is filled on write and
    // the app-owned tail is left to the importer.
    rows.push([
      jurisdiction.jurisdiction_ocdid,
      jurisdiction.name || "",
      false,
      jurisdiction.url || "",
      jurisdiction.population || "",
      jurisdiction.level || "",
    ]);
  });
}

/**
 * A rejecting dropdown: an ocdid off this list is one the import refuses anyway. The cell holds
 * the raw ocdid — Sheets filters by substring, and an ocdid carries its own place slug.
 */
function pointOcdidAtJurisdictions(sheet, ocdidRange) {
  const column = headerIndex(sheet, "jurisdiction_ocdid");
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInRange(ocdidRange, true)
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
