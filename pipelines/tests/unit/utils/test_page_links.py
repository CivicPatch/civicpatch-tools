import pytest
from utils.page_links import PageLink, page_links

pytestmark = pytest.mark.unit

BASE = "https://www.example-county.gov/departments/"


def test_links_keep_their_anchor_text_and_resolve_against_the_page():
    html = b'<nav><a href="board">Board of Commissioners</a></nav> <a href="/files/1.pdf#page=2">Charter</a>'

    assert page_links(html, BASE) == [
        PageLink(url=f"{BASE}board", text="Board of Commissioners"),
        PageLink(url="https://www.example-county.gov/files/1.pdf", text="Charter"),
    ]


def test_two_anchors_on_one_url_are_one_link_holding_both_texts():
    html = b'<a href="/c"><img src="x.png"></a> <a href="/c">Read more</a> <a href="/c">City Charter</a>'

    assert page_links(html, BASE) == [PageLink(url="https://www.example-county.gov/c", text="Read more City Charter")]


def test_what_is_not_a_web_link_is_left_out():
    html = b'<a href="mailto:clerk@example.gov">Clerk</a> <a href="tel:5551234">Call</a> <a href="javascript:void(0)">Menu</a>'

    assert page_links(html, BASE) == []
