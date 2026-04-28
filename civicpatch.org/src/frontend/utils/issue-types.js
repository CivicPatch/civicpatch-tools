export const ISSUE_TYPE = {
  UNRECOGNIZED_ROLE:    "unrecognized_role",
  PIPELINE_ERROR:       "pipeline_error",
  NO_INFO:              "no_info",
  DOMAIN_INACTIVE:      "domain_inactive",
  DOMAIN_REDIRECTED:    "domain_redirected",
  DOMAIN_INACTIVE_FIXED: "domain_inactive_fixed",
};

export const KNOWN_ISSUE_TYPES = [
  { value: ISSUE_TYPE.PIPELINE_ERROR,        label: "Pipeline error",              category: "error" },
  { value: ISSUE_TYPE.NO_INFO,               label: "No info",                     category: "error" },
  { value: ISSUE_TYPE.DOMAIN_INACTIVE,       label: "Domain inactive",             category: "error" },
  { value: ISSUE_TYPE.UNRECOGNIZED_ROLE,     label: "Unrecognized role",           category: "issue" },
  { value: ISSUE_TYPE.DOMAIN_INACTIVE_FIXED, label: "Domain inactive — fix ready", category: "issue" },
  { value: ISSUE_TYPE.DOMAIN_REDIRECTED,     label: "Domain redirected",           category: "issue" },
];
