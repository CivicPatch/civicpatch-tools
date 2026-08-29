/**
 * Builds the civicpatch data-entry spreadsheet: tabs, headers, protection.
 *
 * Standalone on purpose — a script bound to the spreadsheet is editable by everyone with Edit
 * access to it, which is every volunteer. This one opens the sheet by id and runs as whoever
 * authorized it, so there is no service account and no key anywhere.
 *
 * Idempotent. It never deletes anything on Entry[Roster], where the typing happens, and carries
 * the importer's own columns forward on the tabs it rewrites.
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

// Jurisdictions is the reference list and the roster dropdown's source at once: Sheets
// validation can only point at a range inside the same file.
const LIVE_JURISDICTIONS_TAB = "Live[Jurisdictions]";
const LIVE_PEOPLE_TAB = "Live[People]";
const LIVE_POSTS_TAB = "Live[Posts]";

// Written by the import, not by this script. A setup run must carry them forward or it erases
// the last import's report on a tab it also owns.
const IMPORT_REPORT = ["rows"].concat(APP_OWNED);

const LIVE_JURISDICTION_HEADERS = [
  "jurisdiction_ocdid",
  "name",
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
  "post_label",
  "role_id",
  "division_ocdid",
];

// `/search` is a public route, so this needs no credential. 50 is its `MAX_SEARCH_LIMIT`.
// Apps Script runs on Google's network and cannot reach localhost, so this is always a
// deployed instance — override with the CIVICPATCH_URL script property.
const DEFAULT_CIVICPATCH_URL = "https://civicpatch.org";
const SEARCH_PAGE_SIZE = 50;
// The bulk reads cap at 500 a page, so a state is a handful of requests rather than one a town.
const BULK_PAGE_SIZE = 500;

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
    name: "CIVICPATCH_API_KEY",
    required: true,
    about: "mint one at /settings → API keys; the bulk reads are signed-in only",
  },
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
    jurisdictions.getRange(2, 1, Math.max(jurisdictions.getLastRow() - 1, 1), 1),
  );
  refreshLiveTabs(spreadsheet);

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

function apiKey() {
  const key =
    PropertiesService.getScriptProperties().getProperty("CIVICPATCH_API_KEY");
  if (!key) {
    throw new Error(
      "CIVICPATCH_API_KEY is not set. Mint one at /settings → API keys.",
    );
  }
  // The header takes the bare key, not "Bearer <key>".
  return { Authorization: key };
}

/**
 * Every page of a state-scoped bulk read: page one gives the count, the rest go together.
 */
function fetchStatePages(path) {
  const headers = apiKey();
  const first = fetchAllJson([bulkPageUrl(path, 1)], headers)[0];
  if (!first) {
    throw new Error(
      "Could not read " +
        civicpatchUrl() +
        path +
        " for " +
        ENTRY_STATE +
        ". Check CIVICPATCH_API_KEY is valid and belongs to a maintainer.",
    );
  }

  const remaining = [];
  for (var page = 2; page <= first.total_pages; page++) {
    remaining.push(bulkPageUrl(path, page));
  }
  return [first].concat(
    fetchAllJson(remaining, headers).filter(function (body) {
      return body;
    }),
  );
}

function bulkPageUrl(path, page) {
  return (
    civicpatchUrl() +
    path +
    "?state=" +
    encodeURIComponent(ENTRY_STATE) +
    "&per_page=" +
    BULK_PAGE_SIZE +
    "&page=" +
    page
  );
}

/** Independent requests sent together — round trips dominate. A bad one is null, not a throw. */
function fetchAllJson(urls, headers) {
  const requests = urls.map(function (url) {
    return { url: url, muteHttpExceptions: true, headers: headers || {} };
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

  const sheet = writeJurisdictions(spreadsheet, rows);
  // Column A only: over every column, requireValueInRange would accept a name as an ocdid.
  return sheet;
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

/**
 * Rewrites the jurisdiction list, keeping whatever the importer last reported.
 *
 * The list itself is a projection and gets replaced wholesale, but `rows`/`status`/`error`/
 * `last_import_at` belong to the import. Carried forward by ocdid, so they survive the list
 * being reordered or growing underneath them.
 */
function writeJurisdictions(spreadsheet, rows) {
  const sheet =
    spreadsheet.getSheetByName(LIVE_JURISDICTIONS_TAB) ||
    spreadsheet.insertSheet(LIVE_JURISDICTIONS_TAB);
  const reported = importReportByOcdid(sheet);

  const withReport = rows.map(function (row) {
    const carried = reported[row[0]] || {};
    return LIVE_JURISDICTION_HEADERS.map(function (header, index) {
      if (IMPORT_REPORT.indexOf(header) !== -1) return carried[header] || "";
      return index < row.length ? row[index] : "";
    });
  });

  return writeReferenceTab(
    spreadsheet,
    LIVE_JURISDICTIONS_TAB,
    LIVE_JURISDICTION_HEADERS,
    withReport,
  );
}

/** What the importer last wrote, keyed by ocdid, so a rewrite does not erase it. */
function importReportByOcdid(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return {};
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const ocdidColumn = headers.indexOf("jurisdiction_ocdid");
  if (ocdidColumn === -1) return {};

  const reported = {};
  sheet
    .getRange(2, 1, lastRow - 1, sheet.getLastColumn())
    .getValues()
    .forEach(function (row) {
      const ocdid = String(row[ocdidColumn] || "").trim();
      if (!ocdid) return;
      const carried = {};
      IMPORT_REPORT.forEach(function (header) {
        const at = headers.indexOf(header);
        if (at !== -1) carried[header] = row[at];
      });
      reported[ocdid] = carried;
    });
  return reported;
}

function collectJurisdictions(rows, body) {
  (body.data || []).forEach(function (jurisdiction) {
    // Positions match LIVE_JURISDICTION_HEADERS up to `level`; `rows` and the app-owned tail
    // are the importer's to fill, and `writeReferenceTab` pads them.
    rows.push([
      jurisdiction.jurisdiction_ocdid,
      jurisdiction.name || "",
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

/* ── The Live tabs ─────────────────────────────────────────────────────────── */

/**
 * What civicpatch already holds for the whole state, so a curator matches existing wording
 * instead of minting "Selectboard Member" next to "Select Board Member".
 */
function refreshLiveTabs(spreadsheet) {
  writeReferenceTab(
    spreadsheet,
    LIVE_PEOPLE_TAB,
    LIVE_PEOPLE_HEADERS,
    livePeopleRows(),
  );
  writeReferenceTab(
    spreadsheet,
    LIVE_POSTS_TAB,
    LIVE_POST_HEADERS,
    livePostRows(),
  );
}

function livePeopleRows() {
  const rows = [];
  fetchStatePages("/api/v1/people/bulk").forEach(function (body) {
    (body.data || []).forEach(function (person) {
      // Someone with no open membership still belongs here — they are exactly the person about
      // to be re-added under a slightly different spelling.
      const memberships = (person.memberships || []).length
        ? person.memberships
        : [{}];
      memberships.forEach(function (membership) {
        rows.push(personRow(person.jurisdiction_ocdid, person, membership));
      });
    });
  });
  Logger.log(LIVE_PEOPLE_TAB + ": " + rows.length + " rows");
  return rows;
}

function livePostRows() {
  const rows = [];
  fetchStatePages("/api/v1/posts/bulk").forEach(function (body) {
    (body.data || []).forEach(function (post) {
      rows.push([
        post.jurisdiction_ocdid,
        post.label || "",
        post.role_id || "",
        post.division_ocdid || "",
      ]);
    });
  });
  Logger.log(LIVE_POSTS_TAB + ": " + rows.length + " posts");
  return rows;
}

function personRow(ocdid, person, membership) {
  return [
    ocdid,
    person.name || "",
    membership.post_label || "",
    membership.label || "",
    joined(person.urls),
    joined(person.phones),
    joined(person.emails),
    person.cdn_image || person.image || "",
    person.start_date || "",
    person.end_date || "",
    joined(person.other_names),
    joined(person.source_urls),
  ];
}

function joined(values) {
  return (values || []).join("; ");
}

/** Every distinct, non-empty ocdid in a sheet's `jurisdiction_ocdid` column. */
function ocdidsIn(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  const column = headerIndex(sheet, "jurisdiction_ocdid");
  const seen = {};
  const ocdids = [];
  sheet
    .getRange(2, column, lastRow - 1, 1)
    .getValues()
    .forEach(function (row) {
      const ocdid = String(row[0] || "").trim();
      if (!ocdid || seen[ocdid]) return;
      seen[ocdid] = true;
      ocdids.push(ocdid);
    });
  return ocdids;
}

/** Rewritten whole: these are projections, and a stale row shows a seat that no longer exists. */
function writeReferenceTab(spreadsheet, name, headers, rows) {
  const sheet =
    spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
  sheet.clear();
  sheet
    .getRange(1, 1, 1, headers.length)
    .setValues([headers])
    .setFontWeight("bold")
    .setBackground(HEADER_BACKGROUND);
  sheet.setFrozenRows(1);
  if (rows.length) {
    // Padded to the header width: a caller that leaves the app-owned tail to the importer
    // hands back a short row, and Sheets rejects a mismatched range outright.
    const padded = rows.map(function (row) {
      return headers.map(function (_, index) {
        return index < row.length ? row[index] : "";
      });
    });
    sheet.getRange(2, 1, padded.length, headers.length).setValues(padded);
  }
  protectRange(sheet, sheet.getDataRange(), name + " (app-owned)");
  return sheet;
}
