"""Pipeline 3's tuning knobs in one place: what a run waits for, spends and settles for."""

# Scraping a page (step 2)
PAGE_DEFAULT_TIMEOUT_MS = 30000
PAGE_NAVIGATION_TIMEOUT_MS = 15000

MAX_SCRAPE_ATTEMPTS = 2

DOM_READY_TIMEOUT_MS = 5000
LAZY_RENDER_SETTLE_MS = 2000
POST_LAZY_NETWORKIDLE_TIMEOUT_MS = 5000

SPA_HYDRATION_TIMEOUT_MS = 10000
SPA_SETTLE_MS = 2000
SPA_NETWORKIDLE_TIMEOUT_MS = 8000

IMAGE_DOWNLOAD_TIMEOUT_S = 5

# Playwright waits 30s for a hidden button to become clickable; a real accordion responds at once.
ACCORDION_CLICK_TIMEOUT_MS = 2000

# Reading a page (step 4)
MINIMUM_NUM_PEOPLE = 5
CHUNK_OVERLAP_CHARS = 500
# Above the longest finished relevance call seen (6,970); a runaway reasoning loop fails at half the time.
RELEVANCE_MAX_OUTPUT_TOKENS = 8_192
# Over 639 calls the longest that finished took 16,152 tokens and three ran to 16,384 and failed;
# capped at 4,096 the 870 prod labels got the same answers.
MATCH_MAX_OUTPUT_TOKENS = 4_096

# Expected divisions come from the division_ocdids on the roster we already hold, so they have
# the same staleness as required_data: a ward that was renamed, merged or dropped leaves a
# target no scrape can reach. Floored at one so it stays a real signal — a jurisdiction with
# divisions must still place somebody in one, it just need not place everybody.
DIVISION_REQUIREMENT_TOLERANCE = 2

# When to stop crawling (transitions)
# `required_data` is the size of the roster we already hold, so it is an expectation, not a
# fact — a council that lost a member leaves it permanently unreachable. Seattle, 2026-08-17:
# 10 found against 11 expected, both target flags satisfied, and the run crawled to its page
# cap for the missing one. Treated as a target to get close to rather than a wall.
DATA_REQUIREMENT_TOLERANCE = 2
