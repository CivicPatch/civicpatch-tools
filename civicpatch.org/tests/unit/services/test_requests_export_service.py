import pytest
from core.export import (
    _changed_field_names,
    _extract_fields,
    _flatten_official,
    _request_to_rows,
)


def _official(id="abc", name="Jane Doe", office_name="Mayor", office_division="ocd-division/x",
              phones=None, emails=None, urls=None, source_urls=None,
              other_names=None, start_date=None, end_date=None, updated_at=None):
    return {
        "id": id,
        "name": name,
        "office": {"name": office_name, "division_ocdid": office_division},
        "phones": phones or [],
        "emails": emails or [],
        "urls": urls or [],
        "source_urls": source_urls or [],
        "other_names": other_names or [],
        "start_date": start_date,
        "end_date": end_date,
        "updated_at": updated_at,
    }


def _request(request_id="req-1", jurisdiction_ocdid="ocd-jurisdiction/x", created_at=None,
             result_data=None, review_json=None):
    return {
        "request_id": request_id,
        "jurisdiction_ocdid": jurisdiction_ocdid,
        "created_at": created_at,
        "data_json": result_data or [],
        "review_json": review_json or {},
    }


# --- _changed_field_names ---

def test_changed_field_names_no_changes():
    o = _official(name="Jane Doe", office_name="Mayor", urls=["https://example.com"])
    assert _changed_field_names(o, o) == []


def test_changed_field_names_detects_name_change():
    existing = _official(name="Jane Doe")
    pr = _official(name="Jane Smith")
    assert "name" in _changed_field_names(existing, pr)


def test_changed_field_names_case_insensitive():
    existing = _official(name="jane doe")
    pr = _official(name="JANE DOE")
    assert _changed_field_names(existing, pr) == []


def test_changed_field_names_trims_whitespace():
    existing = _official(name="  Jane Doe  ")
    pr = _official(name="Jane Doe")
    assert _changed_field_names(existing, pr) == []


def test_changed_field_names_detects_office_name_change():
    existing = _official(office_name="Mayor")
    pr = _official(office_name="Mayor Pro Tempore")
    assert "office.name" in _changed_field_names(existing, pr)


def test_changed_field_names_detects_url_change():
    existing = _official(urls=["https://old.example.com"])
    pr = _official(urls=["https://new.example.com"])
    assert "urls" in _changed_field_names(existing, pr)


def test_changed_field_names_multiple_changes():
    existing = _official(name="Jane", phones=["555-0001"])
    pr = _official(name="Jane Smith", phones=["555-9999"])
    changed = _changed_field_names(existing, pr)
    assert "name" in changed
    assert "phones" in changed


# --- _extract_fields ---

def test_extract_fields_joins_lists():
    o = _official(phones=["555-1234", "555-5678"], emails=["a@b.com", "c@d.com"])
    fields = _extract_fields(o)
    assert fields["phones"] == "555-1234 | 555-5678"
    assert fields["emails"] == "a@b.com | c@d.com"


def test_extract_fields_empty_lists():
    o = _official()
    fields = _extract_fields(o)
    assert fields["phones"] == ""
    assert fields["urls"] == ""


def test_extract_fields_sanitizes_formula_injection():
    o = _official(name="=HYPERLINK(\"evil.com\")")
    fields = _extract_fields(o)
    assert fields["name"].startswith("'")


def test_extract_fields_sanitizes_plus_prefix():
    o = _official(name="+cmd|' /C calc'!A0")
    fields = _extract_fields(o)
    assert fields["name"].startswith("'")


def test_extract_fields_safe_values_unchanged():
    o = _official(name="Jane Doe", office_name="Mayor")
    fields = _extract_fields(o)
    assert fields["name"] == "Jane Doe"
    assert fields["office_name"] == "Mayor"


def test_extract_fields_office_from_nested():
    o = _official(office_name="Council Member", office_division="ocd-division/tx")
    fields = _extract_fields(o)
    assert fields["office_name"] == "Council Member"
    assert fields["office_division_ocdid"] == "ocd-division/tx"


# --- _request_to_rows (diff classification) ---

def test_request_to_rows_added():
    official = _official(id="new-1", name="New Person")
    req = _request(result_data=[official])
    rows = _request_to_rows(req, existing_people=[], include_unchanged=False)
    assert len(rows) == 1
    assert rows[0]["diff_status"] == "added"
    assert rows[0]["proposed_name"] == "New Person"
    assert rows[0]["existing_name"] == ""


def test_request_to_rows_removed():
    existing = _official(id="old-1", name="Gone Person")
    req = _request(result_data=[])
    rows = _request_to_rows(req, existing_people=[existing], include_unchanged=False)
    assert len(rows) == 1
    assert rows[0]["diff_status"] == "removed"
    assert rows[0]["existing_name"] == "Gone Person"
    assert rows[0]["proposed_name"] == ""


def test_request_to_rows_changed():
    existing = _official(id="p-1", name="Jane Doe", office_name="Mayor")
    pr = _official(id="p-1", name="Jane Doe", office_name="Mayor Pro Tempore")
    req = _request(result_data=[pr])
    rows = _request_to_rows(req, existing_people=[existing], include_unchanged=False)
    assert len(rows) == 1
    assert rows[0]["diff_status"] == "changed"
    assert "office.name" in rows[0]["changed_fields"]
    assert rows[0]["existing_office_name"] == "Mayor"
    assert rows[0]["proposed_office_name"] == "Mayor Pro Tempore"


def test_request_to_rows_unchanged_excluded_by_default():
    official = _official(id="p-1")
    req = _request(result_data=[official])
    rows = _request_to_rows(req, existing_people=[official], include_unchanged=False)
    assert rows == []


def test_request_to_rows_unchanged_included_when_flag_set():
    official = _official(id="p-1", name="Jane Doe")
    req = _request(result_data=[official])
    rows = _request_to_rows(req, existing_people=[official], include_unchanged=True)
    assert len(rows) == 1
    assert rows[0]["diff_status"] == "unchanged"


def test_request_to_rows_review_issues_populated():
    official = _official(id="p-1")
    req = _request(
        result_data=[official],
        review_json={"issues": ["Missing official: John", "Extra official: Jane"]},
    )
    rows = _request_to_rows(req, existing_people=[official], include_unchanged=True)
    assert rows[0]["review_issues"] == "Missing official: John | Extra official: Jane"


def test_request_to_rows_mixed():
    added = _official(id="new-1", name="Added")
    removed = _official(id="old-1", name="Removed")
    existing_changed = _official(id="chg-1", name="Before")
    pr_changed = _official(id="chg-1", name="After")
    unchanged = _official(id="same-1", name="Same")

    req = _request(result_data=[added, pr_changed, unchanged])
    existing_people = [removed, existing_changed, unchanged]

    rows = _request_to_rows(req, existing_people=existing_people, include_unchanged=False)
    statuses = {r["diff_status"] for r in rows}
    assert statuses == {"added", "removed", "changed"}
    assert len(rows) == 3


def test_request_to_rows_changed_fields_empty_for_added():
    official = _official(id="new-1")
    req = _request(result_data=[official])
    rows = _request_to_rows(req, existing_people=[], include_unchanged=False)
    assert rows[0]["changed_fields"] == ""


def test_request_to_rows_changed_fields_empty_for_removed():
    existing = _official(id="old-1")
    req = _request(result_data=[])
    rows = _request_to_rows(req, existing_people=[existing], include_unchanged=False)
    assert rows[0]["changed_fields"] == ""
