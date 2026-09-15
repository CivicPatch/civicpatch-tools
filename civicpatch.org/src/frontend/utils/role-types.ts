// Role vocabulary the frontend shares with the backend's role derivation. Mirrors
// `core/post_derivation.py` — the two languages keep their own copy since neither can
// import the other, but each side names this in exactly one place.

// A proposal's `role_id` when the scrape found a seat but couldn't name its role at all.
export const UNMATCHED_ROLE_ID = "unmatched";
