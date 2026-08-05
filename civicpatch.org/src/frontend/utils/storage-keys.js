// Every localStorage key the app uses is declared here, so what we store — and
// whether it cleans up — is answerable from one file.
//
// Three places hold these strings literally and cannot import them: the pre-paint
// theme script in templates/layouts/base.html (mirrored in _mock-person-modal.html),
// and the seeds in e2e/. Renaming a key here means updating those by hand.
export const STORAGE_KEYS = {
    THEME: "app:theme", // forever
    DEFAULT_STATE: "app:default-state", // forever; removed on logout
    QUEUE_VIEW: "app:queue-view", // forever
    ISSUES_OPEN_SECTIONS: "issues-page:open-sections", // forever
    DAILY_GOAL: "review:daily-goal", // forever
    SWEPT_AT: "app:storage-swept-at", // forever; the sweep's own bookkeeping
};

// A prefix, not a key: one entry per pull request opened, so unlike the
// singletons above this family grows.
export const ISSUE_CHECKS_PREFIX = "review:issue-checks:";
