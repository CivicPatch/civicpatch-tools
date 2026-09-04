"""Pure projections of civicpatch data into spreadsheet rows.

One module per tab, each owning its `HEADERS` (the column order is the contract) and a
`to_rows`. No I/O — `services.roster_sheet` does the writing.
"""

# Pixel widths keyed by what the column holds, not by which tab it is on: `person_id` is the
# same uuid wherever it appears, so it gets the same width everywhere.
#
# Roughly 7px a character at the default font, sized against measured content: p99 length for
# the short columns, p90 for the long ones. Sizing urls to p99 would mean 800px and
# `source_urls` to p99 would mean 3,500px, which buys the outlier at everyone else's expense.
#
# Re-applied on every sync, so a curator who drags a column wider loses it on the next run.
# Acceptable while these tabs are app-owned reference — revisit if they ever become editable.
_DEFAULT_WIDTH = 160

_WIDTHS = {
    # A key you filter on, not prose you read. ~80 characters, and the distinguishing part —
    # the place slug — is at the *end*, so no realistic width reveals it; widening only shows
    # more of the constant `ocd-jurisdiction/country:us/state:xx/` prefix.
    "jurisdiction_ocdid": 240,
    "post_division_ocdid": 300,
    # Machine keys. Nobody reads a uuid — narrow enough to scroll past, wide enough to see a
    # blank where one should not be.
    "person_id": 80,
    "post_id": 80,
    "membership_id": 80,
    # Names and labels: the whole point of the reference tabs is matching wording, so these
    # must not truncate.
    "person_name": 160,
    # Empty on 92% of rows (p90 is zero characters). Sized for the exception, not the outlier.
    "person_other_names": 120,
    "post_label": 220,
    "post_role_id": 180,
    "membership_label": 200,
    "membership_source_labels": 240,
    "name": 200,
    # Contact, measured. p90 of the 72% that have one is 32 characters — p99's 52 is one row
    # in a hundred and not worth 150px on every screen.
    "person_emails": 240,
    # 99.5% of people have exactly one url (104 of 19,718 have two, joined into this one
    # cell and so not individually clickable). Sized to the single-url p90 of 74 characters.
    "person_urls": 520,
    "person_image": 240,
    # Deliberately under-sized. p90 is 120 characters and p99 is 504 — a scrape artifact
    # nobody reads end to end, and fitting it would push everything else off-screen.
    "person_source_urls": 260,
    # One number is 14 characters; the p99 of 40 is somebody with two.
    "person_phones": 140,
    "url": 300,
    # Fixed-shape values. A partial date is at most `YYYY-MM-DD`, a timestamp ~25 characters.
    "membership_start_date": 110,
    "membership_end_date": 110,
    "membership_first_seen_at": 175,
    "membership_last_seen_at": 175,
    "membership_closed_at": 175,
    "person_updated_at": 175,
    "post_headcount": 90,
    "population": 100,
    "level": 90,
}


def widths_for(headers: list[str]) -> list[int]:
    return [_WIDTHS.get(header, _DEFAULT_WIDTH) for header in headers]
