export const ISSUE_TYPE = {
  UNRECOGNIZED_ROLE:       "unrecognized_role",
  PIPELINE_ERROR:          "pipeline_error",
  NO_INFO:                 "no_info",
  DOMAIN_INACTIVE:         "domain_inactive",
  DOMAIN_NAVIGATION_ERROR: "domain_navigation_error",
};

export const KNOWN_ISSUE_TYPES = [
  { value: ISSUE_TYPE.PIPELINE_ERROR,          label: "Pipeline error",     category: "error" },
  { value: ISSUE_TYPE.NO_INFO,                 label: "No info",            category: "error" },
  { value: ISSUE_TYPE.DOMAIN_INACTIVE,         label: "Domain inactive",    category: "error" },
  { value: ISSUE_TYPE.DOMAIN_NAVIGATION_ERROR, label: "Navigation error",   category: "error" },
  { value: ISSUE_TYPE.UNRECOGNIZED_ROLE,       label: "Unrecognized role",  category: "issue" },
];
