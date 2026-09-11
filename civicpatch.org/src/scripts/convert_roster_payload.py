"""
Convert a jurisdiction_id-keyed roster payload into rows pasteable under Entry[Roster]'s
header (`jurisdiction_ocdid, name, source_url, email, phone, image, label`).

Standalone: no app imports, no database, no docker. Runs anywhere with plain python3. The
source's `jurisdiction_id` (e.g. "jurisdiction-ca-menlo-park") becomes the ocdid it implies
("ocd-jurisdiction/country:us/state:ca/place:menlo_park/government") by string reconstruction
alone — the same thing a hand-typed ocdid always was, right or wrong, is checked at import,
per jurisdiction, not here.

Usage:
    python3 convert_roster_payload.py payload.tsv
    python3 convert_roster_payload.py payload.tsv roster.tsv

Reads tab-separated input from the given file, with or without a header row (columns are
positional, matching the source's own header). Prints Entry[Roster]-ready TSV to the terminal,
or writes it to a file if a second argument names one.
"""

import csv
import sys

SOURCE_COLUMNS = [
    "person_id",
    "jurisdiction_id",
    "name",
    "given_name",
    "family_name",
    "status",
    "source_url",
    "email",
    "phone",
    "image",
    "aliases",
    "source_ids",
    "civicpatch_id",
    "notes",
    "accessed_date",
]

ROSTER_COLUMNS = ["jurisdiction_ocdid", "name", "source_url", "email", "phone", "image", "label"]


def _ocdid_from_jurisdiction_id(jurisdiction_id: str) -> str | None:
    """"jurisdiction-ca-menlo-park" -> ".../state:ca/place:menlo_park/government", or None for
    anything that isn't that shape — a blank row, a stray header, a source that changed."""
    parts = jurisdiction_id.split("-")
    if len(parts) < 3 or parts[0] != "jurisdiction":
        return None
    _, state, *place_parts = parts
    place = "_".join(place_parts)
    return f"ocd-jurisdiction/country:us/state:{state}/place:{place}/government"


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: convert_roster_payload.py payload.tsv [roster.tsv]", file=sys.stderr)
        sys.exit(1)

    outfile = open(sys.argv[2], "w", newline="") if len(sys.argv) > 2 else sys.stdout

    with open(sys.argv[1], newline="") as infile:
        reader = csv.DictReader(infile, delimiter="\t", fieldnames=SOURCE_COLUMNS)
        source_rows = [row for row in reader if row["person_id"] != "person_id"]

    writer = csv.writer(outfile, delimiter="\t")
    writer.writerow(ROSTER_COLUMNS)
    written = 0
    for line, row in enumerate(source_rows, start=1):
        ocdid = _ocdid_from_jurisdiction_id(row["jurisdiction_id"] or "")
        if ocdid is None:
            print(f"skipped row {line}: bad jurisdiction_id {row['jurisdiction_id']!r}", file=sys.stderr)
            continue
        writer.writerow(
            [ocdid, row["name"], row["source_url"], row["email"], row["phone"], row["image"], ""]
        )
        written += 1

    if outfile is not sys.stdout:
        outfile.close()
        print(f"wrote {written} row(s) to {sys.argv[2]}", file=sys.stderr)


if __name__ == "__main__":
    main()
