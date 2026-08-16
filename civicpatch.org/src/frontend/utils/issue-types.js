export const ISSUE_TYPE = {
  // TBD remove: the pipeline stopped emitting these 2026-08-16; kept until the existing
  // rows are drained. Drop the resolve-modal form and issue-row branch with it.
  UNRECOGNIZED_ROLE:       "unrecognized_role",
  PIPELINE_ERROR:          "pipeline_error",
  NO_INFO:                 "no_info",
  DOMAIN_INACTIVE:         "domain_inactive",
  DOMAIN_NAVIGATION_ERROR: "domain_navigation_error",
  MERGE_FAILED:            "merge_failed",
  USER_REPORTED:           "user_reported",
};

export const KNOWN_ISSUE_TYPES = [
  { value: ISSUE_TYPE.PIPELINE_ERROR,          label: "Pipeline error" },
  { value: ISSUE_TYPE.NO_INFO,                 label: "No info" },
  { value: ISSUE_TYPE.DOMAIN_INACTIVE,         label: "Domain inactive" },
  { value: ISSUE_TYPE.DOMAIN_NAVIGATION_ERROR, label: "Navigation error" },
  { value: ISSUE_TYPE.UNRECOGNIZED_ROLE,       label: "Unrecognized role" },
  { value: ISSUE_TYPE.MERGE_FAILED,            label: "Merge failed" },
  { value: ISSUE_TYPE.USER_REPORTED,           label: "User reported" },
];
