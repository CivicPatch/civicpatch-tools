export const ISSUE_TYPE = {
  PIPELINE_ERROR: "pipeline_error",
  NO_ROSTER_FOUND: "no_roster_found",
  DOMAIN_INACTIVE: "domain_inactive",
  DOMAIN_NAVIGATION_ERROR: "domain_navigation_error",
  MERGE_FAILED: "merge_failed",
  USER_REPORTED: "user_reported",
  COST_CAP_REACHED: "cost_cap_reached",
};

export const KNOWN_ISSUE_TYPES = [
  { value: ISSUE_TYPE.PIPELINE_ERROR, label: "Pipeline error" },
  { value: ISSUE_TYPE.NO_ROSTER_FOUND, label: "No roster found" },
  { value: ISSUE_TYPE.DOMAIN_INACTIVE, label: "Domain inactive" },
  { value: ISSUE_TYPE.DOMAIN_NAVIGATION_ERROR, label: "Navigation error" },
  { value: ISSUE_TYPE.MERGE_FAILED, label: "Merge failed" },
  { value: ISSUE_TYPE.USER_REPORTED, label: "User reported" },
  { value: ISSUE_TYPE.COST_CAP_REACHED, label: "Cost cap reached" },
];
