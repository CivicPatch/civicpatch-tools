import os
import pytest
from jobs.people_collector.steps.step_04_preprocess_page_content.clean_html import clean_html
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

       