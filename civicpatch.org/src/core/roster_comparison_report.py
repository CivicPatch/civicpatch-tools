"""A saved run as Markdown, so every agent reports the same numbers, word for word."""

from core.roster_comparison_rates import civicpatch_has_no_one
from schemas.roster_comparisons import ComparedField, ComparisonRates, RosterComparisonSummary

MAX_ORGANIZATIONS_NAMED = 8

FIELD_NAMES = {
    ComparedField.ROLE: "Role",
    ComparedField.EMAILS: "Emails",
    ComparedField.PHONES: "Phones",
    ComparedField.URLS: "Links",
    ComparedField.START_DATE: "Start date",
}


def report_markdown(summary: RosterComparisonSummary, names: dict[str, str]) -> str:
    """`names`: jurisdiction ocdid → name, for the run's jurisdictions."""
    sections = [
        _heading(summary),
        _people(summary.run.rates),
        _fields(summary.run.rates),
        _worth_a_look(summary, names),
        f"[Open the comparison]({summary.page_url})",
    ]
    return "\n\n".join(section for section in sections if section) + "\n"


def _heading(summary: RosterComparisonSummary) -> str:
    run, outcomes = summary.run, summary.run.rates.outcomes
    rows = outcomes.matched + outcomes.possible_match + outcomes.only_in_uploaded_data
    lines = [
        f"## {run.state.upper()} roster comparison",
        "",
        f"**{_count(len(summary.jurisdictions), 'jurisdiction')}** compared, from {_count(rows, 'row')}. "
        f"{_count(run.jurisdictions_not_named, 'jurisdiction')} of the state had no rows and were not compared.",
    ]
    if summary.organizations:
        lines.append(f"Organizations compared: {_organizations_named(summary.compared_organizations)}.")
    return "\n".join(lines)


def _organizations_named(compared: list[str]) -> str:
    if not compared:
        return "none"
    if len(compared) <= MAX_ORGANIZATIONS_NAMED:
        return ", ".join(compared)
    shown = ", ".join(compared[:MAX_ORGANIZATIONS_NAMED])
    return f"{shown} and {len(compared) - MAX_ORGANIZATIONS_NAMED} more, listed on the page"


def _people(rates: ComparisonRates) -> str:
    outcomes = rates.outcomes
    lines = [
        "### People",
        "| Outcome | Count |",
        "|---|---|",
        f"| Matched | {outcomes.matched} |",
        f"| Possible match, to review | {outcomes.possible_match} |",
        f"| Only in your data | {outcomes.only_in_uploaded_data} |",
        f"| Only in civicpatch | {outcomes.only_in_civicpatch} |",
    ]
    if outcomes.only_in_civicpatch_not_compared:
        lines += ["", f"Not counted: {outcomes.only_in_civicpatch_not_compared} of civicpatch's people in organizations not compared."]
    return "\n".join(lines)


def _fields(rates: ComparisonRates) -> str:
    matched = rates.outcomes.matched
    if not matched:
        return ""
    supplied = [field for field, counts in rates.fields.items() if counts.uploaded_data_has_it]
    lines = [f"### Fields, over {_count(matched, 'matched person', 'matched people')}"]
    if supplied:
        lines += ["| Field | Agree | Conflict |", "|---|---|---|"]
        lines += [
            f"| {FIELD_NAMES[field]} | {_percent(rates.fields[field].agreement, matched)} "
            f"| {_percent(rates.fields[field].conflict, matched)} |"
            for field in supplied
        ]
    missing = [FIELD_NAMES[field] for field in ComparedField if field not in supplied]
    if missing:
        lines += ["", f"Your data had none of: {', '.join(missing)}."]
    lines += [
        "",
        f"{_count(rates.people_with_conflicts, 'matched person', 'matched people')} "
        f"({_percent(rates.people_with_conflicts, matched)}) conflict in at least one field. "
        "A person can conflict in more than one field.",
    ]
    return "\n".join(lines)


def _worth_a_look(summary: RosterComparisonSummary, names: dict[str, str]) -> str:
    rates = summary.run.rates
    empty = [
        names.get(jurisdiction.jurisdiction_ocdid, jurisdiction.jurisdiction_ocdid)
        for jurisdiction in summary.jurisdictions
        if civicpatch_has_no_one(jurisdiction.rates.outcomes)
    ]
    items = []
    if rates.rows_with_warnings:
        items.append(
            f"- {_count(rates.rows_with_warnings, 'row has', 'rows have')} warnings "
            "(invalid email or phone, unrecognised role, or a possible duplicate)."
        )
    if empty:
        items.append(f"- civicpatch has no one yet in {_count(len(empty), 'jurisdiction')}: {', '.join(sorted(empty))}.")
    if summary.run.corrections:
        items.append(f"- The agent's corrections: {len(summary.run.corrections)} (listed on the page).")
    return "\n".join(["### Worth a look", *items]) if items else ""


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else plural or singular + 's'}"


def _percent(part: int, whole: int) -> str:
    """Rounded half up, as the page rounds (`Math.round`), so the two agree."""
    return "0%" if whole == 0 else f"{(part * 100 + whole // 2) // whole}%"
