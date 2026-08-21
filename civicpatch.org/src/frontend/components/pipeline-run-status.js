export const PIPELINE_RUN_STATUS = {
  PENDING: "PENDING",
  RUNNING: "RUNNING",
  COMPLETED: "SUCCESS",
  ERROR: "ERROR",
  RESOLVED: "RESOLVED",
  CANCELLED: "CANCELLED",
};

// The terminal set used to live here too, duplicating `shared/utils/statuses.py`. Both the
// history rows and the socket payload now carry `is_running`, so nothing on this side has to
// know which statuses end a run.
