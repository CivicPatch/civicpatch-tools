export const ISSUE_TYPE = {
  UNRECOGNIZED_ROLE:    "unrecognized_role",
  PIPELINE_ERROR:       "pipeline_error",
  NO_INFO:              "no_info",
  DOMAIN_INACTIVE:      "domain_inactive",
  DOMAIN_REDIRECTED:    "domain_redirected",
  DOMAIN_INACTIVE_FIXED: "domain_inactive_fixed",
};

// modal_type determines which modal opens when clicking a row action:
//   "role"                  → Resolve modal (opens a PR to fix the role config)
//   "domain_inactive_fixed" → Resolve modal (opens a PR to update the jurisdiction URL)
//   "pipeline_error"        → Pipeline error modal (shows error message + debug links)
//   "debug"                 → Debug links modal (shows workflow/context/storage links)
//   null                    → no modal / no row action button
export const KNOWN_ISSUE_TYPES = [
  { value: ISSUE_TYPE.PIPELINE_ERROR,        label: "Pipeline error",             category: "error", modal_type: "pipeline_error" },
  { value: ISSUE_TYPE.NO_INFO,               label: "No info",                    category: "error", modal_type: "debug" },
  { value: ISSUE_TYPE.DOMAIN_INACTIVE,       label: "Domain inactive",            category: "error", modal_type: "debug" },
  { value: ISSUE_TYPE.UNRECOGNIZED_ROLE,     label: "Unrecognized role",          category: "issue", modal_type: "role" },
  { value: ISSUE_TYPE.DOMAIN_INACTIVE_FIXED, label: "Domain inactive — fix ready", category: "issue", modal_type: "debug" },
  { value: ISSUE_TYPE.DOMAIN_REDIRECTED,     label: "Domain redirected",          category: "issue", modal_type: null },
];
