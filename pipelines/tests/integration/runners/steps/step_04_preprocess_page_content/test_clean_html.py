import os
import pytest
from runners.people_collector.steps.step_04_preprocess_page_content.clean_html import clean_html
from pathlib import Path
from markdownify import markdownify as md

pytestmark = pytest.mark.unit

FIXTURE_DIR = Path(__file__).parent / "fixtures"

def test_nested_images_out_of_headers():
    """Test that images nested within other tags inside headers are moved correctly."""
    input_html = """
    <html>
        <body>
            <h1>
                <a href="some_link.html">
                    Title <img src="header_image.jpg" />
                </a>
            </h1>
            <p>Some content here.</p>
        </body>
    </html>
    """
    expected_output_html = """
<html>
 <body>
  <h1>
   <a href="some_link.html">        Title
   </a>
  </h1>
  <img src="header_image.jpg"/>
  <p>Some content here.</p>
 </body>
</html>
    """
    cleaned_html = clean_html(None, input_html)
    assert ''.join(cleaned_html.split()) == ''.join(expected_output_html.split())

def test_nested_images_in_table_cells():
    """Test that images nested within other tags inside table cells are moved correctly."""
    input_html = """
    <html>
        <body>
            <table>
                <tr>
                    <td>
                        <img src="cell_image.jpg" />
                        Cell content.
                    </td>
                </tr>
            </table>
        </body>
    </html>
    """
    expected_output_html = """
<html>
 <body>
  <table>
   <tr>
    <td>
     <img src="cell_image.jpg"/>
     Cell content.
    </td>
   </tr>
  </table>
 </body>
</html>
    """
    cleaned_html = clean_html(None, input_html)
    assert ''.join(cleaned_html.split()) == ''.join(expected_output_html.split())

def test_with_fixture():
    with open(FIXTURE_DIR / "garland_nested_images" / "input.html", "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    with open(FIXTURE_DIR / "garland_nested_images" / "expected_clean_html.html", "w", encoding="utf-8") as f:
        f.write(cleaned_html)
    #with open(FIXTURE_DIR / "garland_nested_images" / "expected_clean_html.html", "r", encoding="utf-8") as f:
    #    expected_output = f.read()
    #assert ''.join(cleaned_html.split()) == ''.join(expected_output.split())

def test_with_read_more_fixture():
    with open(os.path.join(FIXTURE_DIR, "la_joya_read_more", "input.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    with open(FIXTURE_DIR / "la_joya_read_more" / "expected_clean_html.html", "w", encoding="utf-8") as f:
        f.write(cleaned_html)
    #with open(os.path.join(FIXTURE_DIR, "la_joya_read_more", "expected_clean_html.html"), "r", encoding="utf-8") as f:
    #    expected_output = f.read()
    #assert ''.join(cleaned_html.split()) == ''.join(expected_output.split())

def test_with_flattened_shadow_dom():
    with open(os.path.join(FIXTURE_DIR, "flattened_shadow_dom", "input.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    with open(FIXTURE_DIR / "flattened_shadow_dom" / "expected_clean_html.html", "w", encoding="utf-8") as f:
        f.write(cleaned_html)
    #with open(os.path.join(FIXTURE_DIR, "flattened_shadow_dom", "expected_clean_html.html"), "r", encoding="utf-8") as f:
    #    expected_output = f.read()
    #assert ''.join(cleaned_html.split()) == ''.join(expected_output.split())

def test_with_divs_with_names():
    with open(os.path.join(FIXTURE_DIR, "divs_with_names", "input.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    #with open(FIXTURE_DIR / "divs_with_names" / "expected_clean_html.html", "w", encoding="utf-8") as f:
    #    f.write(cleaned_html)
    with open(os.path.join(FIXTURE_DIR, "divs_with_names", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        expected_output = f.read()
    assert ''.join(cleaned_html.split()) == ''.join(expected_output.split())

def test_with_divs_with_names_2():
    with open(os.path.join(FIXTURE_DIR, "divs_with_names_2", "input.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    #with open(FIXTURE_DIR / "divs_with_names_2" / "expected_clean_html.html", "w", encoding="utf-8") as f:
    #    f.write(cleaned_html)
    with open(os.path.join(FIXTURE_DIR, "divs_with_names_2", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        expected_output = f.read()
    assert ''.join(cleaned_html.split()) == ''.join(expected_output.split())

def test_with_board_of_aldermen():
    with open(os.path.join(FIXTURE_DIR, "board_of_aldermen", "input.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    #with open(FIXTURE_DIR / "board_of_aldermen" / "expected_clean_html.html", "w", encoding="utf-8") as f:
    #    f.write(cleaned_html)
    with open(os.path.join(FIXTURE_DIR, "board_of_aldermen", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        expected_output = f.read()
    assert ''.join(cleaned_html.split()) == ''.join(expected_output.split())

def test_with_wix_site():
    with open(os.path.join(FIXTURE_DIR, "wix_site", "input.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    with open(FIXTURE_DIR / "wix_site" / "expected_clean_html.html", "w", encoding="utf-8") as f:
        f.write(cleaned_html)
    with open(os.path.join(FIXTURE_DIR, "wix_site", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        expected_output = f.read()
    assert ''.join(cleaned_html.split()) == ''.join(expected_output.split())

def test_tmm_email_links_preserved():
    """TMM-style pages: email links wrap an <img> inside nested divs.
    All divs are stripped by clean_html — mailto hrefs must survive."""
    with open(os.path.join(FIXTURE_DIR, "tmm_email_links", "input.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    assert 'href="mailto:' in cleaned_html, "mailto links were dropped during clean_html"


def test_markdownify_preserves_mailto_on_image_only_anchor():
    """<a href="mailto:..."><img></a> — anchor whose only content is an image.
    markdownify must emit the mailto href, not silently drop the link."""
    html = '<a href="mailto:tleverentz@oakleaftexas.org"><img alt="email" src="email.png"></a>'
    result = md(html, keep_inline_images_in=["td", "th", "tr", "h1", "h2", "h3", "h4", "h5", "h6"])
    assert "mailto:tleverentz@oakleaftexas.org" in result


def test_clean_html_strips_data_uri_from_img_src():
    html = '<html><body><img src="data:image/png;base64,abc123==" alt="photo"></body></html>'
    result = clean_html(None, html)
    assert 'data:' not in result
    assert 'alt="photo"' in result


def test_clean_html_strips_data_uri_from_non_img_tag():
    html = '<html><body><source srcset="data:image/webp;base64,xyz"></body></html>'
    result = clean_html(None, html)
    assert 'data:' not in result


def test_clean_html_preserves_normal_src():
    html = '<html><body><img src="https://example.com/photo.jpg" alt="photo"></body></html>'
    result = clean_html(None, html)
    assert 'https://example.com/photo.jpg' in result


def test_tmm_email_links_survive_clean_html_to_markdown():
    """Full clean_html → markdownify chain: mailto hrefs must appear in the final .md output."""
    with open(os.path.join(FIXTURE_DIR, "tmm_email_links", "input.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    cleaned_html = clean_html(None, input_html)
    result = md(cleaned_html, keep_inline_images_in=["td", "th", "tr", "h1", "h2", "h3", "h4", "h5", "h6"])
    with open(os.path.join(FIXTURE_DIR, "tmm_email_links", "expected_preprocessed.md"), "r", encoding="utf-8") as f:
        expected = f.read()
    assert result == expected
    assert "mailto:tleverentz@oakleaftexas.org" in result, "mailto link lost after clean_html → markdownify"
