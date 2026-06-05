import pytest

from shared.utils.yaml_utils import yaml_dump, yaml_load

# A faithful slice of the on-disk people shape: null optionals, single-quoted
# timestamp, nested office, empty lists, and a long no-space URL.
PERSON_DOC = """\
- name: Dave Watterson
  phones: []
  emails:
  - dwatterson@example.org
  office:
    name: Mayor
    division_ocdid: ocd-division/country:us/state:wa/place:tenino
  image: https://example.org/sites/g/files/styles/full/public/media/office-mayor/image/1716/photo.jpg.webp?itok=gnw8ryXI
  jurisdiction_ocdid: ocd-jurisdiction/country:us/state:wa/place:tenino/government
  cdn_image: null
  source_urls:
  - https://example.org/office-mayor
  updated_at: '2025-11-18T19:49:42+00:00'
  start_date: null
  end_date: null
  other_names: []
  id: 24b2a18f-1b04-45d8-b943-902543c9993d
"""

UNICODE_DOC = """\
- name: José Martínez-Núñez
  other_names:
  - José M.
  office:
    name: Concejal — Distrito 3
    division_ocdid: ocd-division/country:us/state:nm/place:doña_ana
"""

COMMENTED_DOC = """\
# keep this header comment
jurisdictions:
- id: ocd-jurisdiction/country:us/state:wa/place:tenino/government  # trailing note
  url: https://example.org
"""


@pytest.mark.parametrize("doc", [PERSON_DOC, UNICODE_DOC, COMMENTED_DOC])
def test_round_trip_is_lossless(doc):
    # The reformat is intentionally byte-changing (null->blank, scalar unwrap), so
    # assert the parsed *data* is identical, not the bytes.
    assert yaml_load(yaml_dump(yaml_load(doc))) == yaml_load(doc)


def test_preserves_comments():
    # The whole reason ruamel is the manager: PyYAML drops these.
    dumped = yaml_dump(yaml_load(COMMENTED_DOC))
    assert "# keep this header comment" in dumped
    assert "# trailing note" in dumped


def test_long_scalars_are_not_wrapped():
    long_url = "https://example.org/" + "a" * 300
    dumped = yaml_dump({"image": long_url})
    assert long_url in dumped.splitlines()[0]


def test_unicode_is_written_literally_not_escaped():
    # ruamel defaults allow_unicode=True; names must not be \u-escaped on disk.
    dumped = yaml_dump([{"name": "José Martínez-Núñez", "office": {"name": "Concejal — Distrito 3"}}])
    assert "José Martínez-Núñez" in dumped
    assert "Concejal — Distrito 3" in dumped
    assert "\\u" not in dumped and "\\x" not in dumped


def test_none_renders_as_explicit_null():
    # Explicit `null` (YAML's canonical, unambiguous null), not ruamel's default blank
    # scalar — pinned so it stays a deliberate choice.
    assert yaml_dump({"cdn_image": None}) == "cdn_image: null\n"
