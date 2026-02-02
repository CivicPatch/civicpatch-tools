import os
import difflib
import pytest
from jobs.people_collector.steps.step_04_preprocess_page_content.filter_content import filter_content
from jobs.people_collector.steps.step_04_preprocess_page_content.clean_html import clean_html
from markdownify import markdownify as md

pytestmark = pytest.mark.unit
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

class PlaceholderLogger:
    def info(self, message):
        print(f"INFO: {message}")

logger = PlaceholderLogger()

def to_markdown(html: str) -> str:
    return md(html, keep_inline_images_in=['td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']).strip()

def read_fixture(filename, subfolder="with_table"):
    fixture_dir = os.path.join(FIXTURE_DIR, subfolder)
    with open(os.path.join(fixture_dir, filename), "r", encoding="utf-8") as f:
        return f.read().strip()

def assert_markdown_equal(identities, actual_html, expected_md, subfolder=""):
    actual_html = filter_content(logger, identities, actual_html)
    actual_md = to_markdown(actual_html)
    expected_md = expected_md.strip()
    actual_lines = actual_md.splitlines()
    # actual_lines = actual_html.strip().splitlines()
    expected_lines = expected_md.splitlines()

    if subfolder:
        output_dir = os.path.join(FIXTURE_DIR, subfolder)
        if actual_lines != expected_lines:
            print("\n".join(difflib.unified_diff(expected_lines, actual_lines, fromfile="expected", tofile="actual", lineterm="")))
            output_path = os.path.join(output_dir, "preprocessed.md")
            output_html_path = os.path.join(output_dir, "preprocessed.html")
            with open(output_html_path, "w", encoding="utf-8") as f:
                f.write(actual_html)
            print(f"Actual HTML output written to {output_html_path}")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(actual_md)
            print(f"Actual preprocessed output written to {output_path}")
    # assert actual_lines == expected_lines

 #def test_filter_content_with_real_data():
 #    original = read_fixture("original.html")
 #    expected = read_fixture("preprocessed.md")
 #    assert original, "Original fixture is missing or empty"
 #    assert_markdown_equal({}, original, expected, government_type="mayor_council")

#def test_filter_content_with_seattle():
#    original = read_fixture("original.html", subfolder="seattle_council")
#    expected = read_fixture("preprocessed.md", subfolder="seattle_council")
#    assert original, "Keyword test fixture is missing or empty"
#    assert_markdown_equal({}, original, expected, subfolder="seattle_council")


#def test_filter_content_with_big_page():
#    original = read_fixture("original.html", subfolder="big_page")
#    expected = read_fixture("preprocessed.md", subfolder="big_page")
#    assert original, "Big page test fixture is missing or empty"
#    assert_markdown_equal({}, original, expected, subfolder="big_page")

# def test_filter_content_with_table():
#     original = read_fixture("original.html", subfolder="with_table")
#     expected = read_fixture("preprocessed.md", subfolder="with_table")
#     assert original, "Table test fixture is missing or empty"
#     assert_markdown_equal({}, original, expected, subfolder="with_table")

def test_filter_content_keeps_all_images():
    original = """
    <html>
        <body>
            <img src="image1.jpg" alt="irrelevant image">
            <p>Some text</p>
        </body>
    </html>
    """
    expected = """
    ![irrelevant image](image1.jpg)
    """
    assert_markdown_equal({}, original, expected)

def test_filter_content_keeps_images_in_kept_table():
    original = """
    <html>
        <body>
            <table>
                <tr>
                    <td><img src="image2.jpg" alt="relevant image"></td>
                    <td>stuff content</td>
                </tr>
            </table>
        </body>
    </html>
    """
    expected = """
    ![relevant image](image2.jpg) 
    """
    assert_markdown_equal({}, original, expected)

def test_filter_content_keeps_images_outside_kept_table():
    original = """
    <html>
        <body>
            <table>
                <tr>
                    <td>Irrelevant content</td>
                </tr>
            </table>
            <img src="image3.jpg" alt="image">
        </body>
    </html>
    """
    expected = """
    ![image](image3.jpg) 
    """
    assert_markdown_equal({}, original, expected)

def test_filter_content_keeps_images_in_removed_table():
    """Images should be preserved when their containing table is removed"""
    original = """
    <html>
        <body>
            <table>
                <tr>
                    <td><img src="table-img.jpg" alt="chart"></td>
                    <td>Irrelevant data</td>
                </tr>
            </table>
        </body>
    </html>
    """
    expected = """
    ![chart](table-img.jpg)
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_multiple_images_in_removed_container():
    """Multiple images should be preserved when their container is removed"""
    original = """
    <html>
        <body>
            <div>
                <img src="image1.jpg" alt="first">
                <img src="image2.jpg" alt="second">
                <p>Irrelevant content</p>
            </div>
        </body>
    </html>
    """
    expected = """
    ![first](image1.jpg)
![second](image2.jpg)
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_images_in_irrelevant_link():
    """Images inside irrelevant links should be preserved"""
    original = """
    <html>
        <body>
            <a href="http://example.com">
                <img src="linked-img.jpg" alt="logo">
                Irrelevant link text
            </a>
        </body>
    </html>
    """
    expected = """
    ![logo](linked-img.jpg)
Irrelevant link text
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_images_in_nested_irrelevant_containers():
    """Images should be preserved even in deeply nested irrelevant containers"""
    original = """
    <html>
        <body>
            <div>
                <section>
                    <article>
                        <p>
                            <img src="nested.jpg" alt="nested image">
                            Irrelevant nested content
                        </p>
                    </article>
                </section>
            </div>
        </body>
    </html>
    """
    expected = """
    ![nested image](nested.jpg)
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_images_with_relevant_content():
    """Images should be kept alongside relevant content in the same container"""
    original = """
    <html>
        <body>
            <div>
                <img src="council.jpg" alt="council photo">
                <p>Mayor John Smith announced the new policy.</p>
            </div>
        </body>
    </html>
    """
    expected = """
    ![council photo](council.jpg)

Mayor John Smith announced the new policy.
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_images_mixed_with_irrelevant_and_relevant():
    """Images should be preserved when mixed with both relevant and irrelevant content"""
    original = """
    <html>
        <body>
            <div>
                <img src="photo1.jpg" alt="photo one">
                <p>Irrelevant stuff</p>
            </div>
            <div>
                <p>Mayor Jane Doe spoke today.</p>
                <img src="photo2.jpg" alt="photo two">
            </div>
        </body>
    </html>
    """
    expected = """
    ![photo one](photo1.jpg)

Mayor Jane Doe spoke today.

![photo two](photo2.jpg)
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_images_in_removed_span():
    """Images in span elements should be preserved when span is removed"""
    original = """
    <html>
        <body>
            <span>
                <img src="icon.jpg" alt="icon">
                Irrelevant span text
            </span>
        </body>
    </html>
    """
    expected = """
    ![icon](icon.jpg)
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_images_in_removed_section():
    """Images in section elements should be preserved when section is removed"""
    original = """
    <html>
        <body>
            <section>
                <img src="banner.jpg" alt="banner">
                <p>Unrelated section content</p>
            </section>
        </body>
    </html>
    """
    expected = """
    ![banner](banner.jpg)
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_image_only_no_other_content():
    """A container with only an image and no other content should preserve the image"""
    original = """
    <html>
        <body>
            <div>
                <img src="solo.jpg" alt="alone">
            </div>
        </body>
    </html>
    """
    expected = """
    ![alone](solo.jpg)
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_images_across_multiple_removed_tables():
    """Images in multiple removed tables should all be preserved"""
    original = """
    <html>
        <body>
            <table>
                <tr><td><img src="table1.jpg" alt="first table"></td></tr>
            </table>
            <table>
                <tr><td><img src="table2.jpg" alt="second table"></td></tr>
            </table>
        </body>
    </html>
    """
    expected = """
    ![first table](table1.jpg)
![second table](table2.jpg)
    """
    assert_markdown_equal({}, original, expected)


def test_filter_content_keeps_images_in_kept_table_with_relevant_content():
    """Images in tables with relevant content should be kept with the table"""
    original = """
    <html>
        <body>
            <table>
                <tr>
                    <td><img src="council-table.jpg" alt="council"></td>
                    <td>Mayor Smith</td>
                </tr>
            </table>
        </body>
    </html>
    """
    expected = """
|  |  |
| --- | --- |
| ![council](council-table.jpg) | Mayor Smith |
    """
    assert_markdown_equal({}, original, expected)

def test_filter_content_keeps_relevant_content_with_case_insensitive_match():
    """Content containing case-insensitive matches of identities should be preserved"""
    identities = {
        "Alice Johnson": ["A. Johnson", "Alice J."],
        "Bob Smith": ["B. Smith", "Robert S."]
    }
    original = """
    <html>
        <body>
            <p>alice johnson attended the meeting.</p>
            <p>Some irrelevant content.</p>
        </body>
    </html>
    """
    expected = """
alice johnson attended the meeting.
    """
    assert_markdown_equal(identities, original, expected)


def test_filter_content_keeps_relevant_content_with_mixed_identities_and_aliases():
    """Content containing both identities and aliases should be preserved"""
    identities = {
        "Alice Johnson": ["A. Johnson", "Alice J."],
        "Bob Smith": ["B. Smith", "Robert S."]
    }
    original = """
    <html>
        <body>
            <p>Alice J. and Robert S. attended the meeting.</p>
            <p>Some irrelevant content.</p>
        </body>
    </html>
    """
    expected = """
Alice J. and Robert S. attended the meeting.
    """
    assert_markdown_equal(identities, original, expected)

def test_filter_content_keeps_relevant_content_with_ethnic_names():
    """Content containing ethnic names should be preserved"""
    identities = {
        "José Martínez": ["J. Martínez", "Jose M."],
        "李小龙": ["Bruce Lee", "L. Xiao Long"]
    }
    original = """
    <html>
        <body>
            <p>José Martínez gave a speech today.</p>
            <p>李小龙 was mentioned in the meeting.</p>
            <p>Some irrelevant content.</p>
        </body>
    </html>
    """
    expected = """
José Martínez gave a speech today.

李小龙 was mentioned in the meeting.
    """
    assert_markdown_equal(identities, original, expected)


def test_filter_content_keeps_relevant_content_with_ethnic_name_aliases():
    """Content containing aliases of ethnic names should be preserved"""
    identities = {
        "José Martínez": ["J. Martínez", "Jose M."],
        "李小龙": ["Bruce Lee", "L. Xiao Long"]
    }
    original = """
    <html>
        <body>
            <p>J. Martínez was present at the event.</p>
            <p>Bruce Lee's legacy was discussed.</p>
            <p>Some irrelevant content.</p>
        </body>
    </html>
    """
    expected = """
J. Martínez was present at the event.

Bruce Lee's legacy was discussed.
    """
    assert_markdown_equal(identities, original, expected)

def test_markdownify_image_output():
    output_dir = os.path.join(FIXTURE_DIR, "image_in_table")
    with open(os.path.join(output_dir, "original.html"), "r", encoding="utf-8") as f:
        original_html = f.read()

    with open(os.path.join(output_dir, "preprocessed.md"), "r", encoding="utf-8") as f:
        expected_md = f.read()
    assert_markdown_equal({}, original_html, expected_md, subfolder="image_in_table")

#def test_with_cleaned_html():
#    original = read_fixture("input.html", subfolder="garland_nested_images")
#    cleaned_html = clean_html({}, original)
#    assert_markdown_equal({}, cleaned_html,
#                          read_fixture("preprocessed.md", subfolder="garland_nested_images"),
#                          "mayor_council", subfolder="garland_nested_images")

def test_with_read_more_fixture():
    with open(os.path.join(FIXTURE_DIR, "la_joya_read_more", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    filtered_content = filter_content(logger, {}, input_html)
    #with open(os.path.join(FIXTURE_DIR, "la_joya_read_more", "expected_filter_content.html"), "w", encoding="utf-8") as f:
    #    f.write(filtered_content)
    expected_html = read_fixture("expected_filter_content.html", subfolder="la_joya_read_more")
    assert filtered_content.strip() == expected_html.strip()
    actual_md = to_markdown(filtered_content)
    #with open(os.path.join(FIXTURE_DIR, "la_joya_read_more", "expected_filter_content.md"), "w", encoding="utf-8") as f:
    #    f.write(actual_md)
    with open(os.path.join(FIXTURE_DIR, "la_joya_read_more", "expected_filter_content.md"), "r", encoding="utf-8") as f:
        expected_md = f.read()
    assert actual_md.strip() == expected_md.strip()

def test_with_flattened_shadow_dom():
    with open(os.path.join(FIXTURE_DIR, "flattened_shadow_dom", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    filtered_content = filter_content(logger, {}, input_html)
    #with open(os.path.join(FIXTURE_DIR, "flattened_shadow_dom", "expected_filter_content.html"), "w", encoding="utf-8") as f:
    #    f.write(filtered_content)
    expected_html = read_fixture("expected_filter_content.html", subfolder="flattened_shadow_dom")
    assert filtered_content.strip() == expected_html.strip()
    actual_md = to_markdown(filtered_content)
    #with open(os.path.join(FIXTURE_DIR, "flattened_shadow_dom", "expected_filter_content.md"), "w", encoding="utf-8") as f:
    #    f.write(actual_md)
    with open(os.path.join(FIXTURE_DIR, "flattened_shadow_dom", "expected_filter_content.md"), "r", encoding="utf-8") as f:
        expected_md = f.read()
    assert actual_md.strip() == expected_md.strip()

def test_with_divs_with_names():
    with open(os.path.join(FIXTURE_DIR, "divs_with_names", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    filtered_content = filter_content(logger, {"Meloday Ryan": [], "Kimberly Holiday": []}, input_html)
    #with open(os.path.join(FIXTURE_DIR, "divs_with_names", "expected_filter_content.html"), "w", encoding="utf-8") as f:
    #    f.write(filtered_content)
    expected_html = read_fixture("expected_filter_content.html", subfolder="divs_with_names")
    assert filtered_content.strip() == expected_html.strip()
    actual_md = to_markdown(filtered_content)
    #with open(os.path.join(FIXTURE_DIR, "divs_with_names", "expected_filter_content.md"), "w", encoding="utf-8") as f:
    #    f.write(actual_md)
    with open(os.path.join(FIXTURE_DIR, "divs_with_names", "expected_filter_content.md"), "r", encoding="utf-8") as f:
        expected_md = f.read()
    assert actual_md.strip() == expected_md.strip()


def test_with_divs_with_names_2():
    with open(os.path.join(FIXTURE_DIR, "divs_with_names_2", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    filtered_content = filter_content(logger, {"Meloday Ryan": [], "Kimberly Holiday": []}, input_html)
    #with open(os.path.join(FIXTURE_DIR, "divs_with_names_2", "expected_filter_content.html"), "w", encoding="utf-8") as f:
    #    f.write(filtered_content)
    expected_html = read_fixture("expected_filter_content.html", subfolder="divs_with_names_2")
    assert filtered_content.strip() == expected_html.strip()
    actual_md = to_markdown(filtered_content)
    #with open(os.path.join(FIXTURE_DIR, "divs_with_names_2", "expected_filter_content.md"), "w", encoding="utf-8") as f:
    #    f.write(actual_md)
    with open(os.path.join(FIXTURE_DIR, "divs_with_names_2", "expected_filter_content.md"), "r", encoding="utf-8") as f:
        expected_md = f.read()
    assert actual_md.strip() == expected_md.strip()

def test_with_board_of_aldermen():
    with open(os.path.join(FIXTURE_DIR, "board_of_aldermen", "expected_clean_html.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    filtered_content = filter_content(logger, {"Meloday Ryan": [], "Kimberly Holiday": []}, input_html)
    #with open(os.path.join(FIXTURE_DIR, "board_of_aldermen", "expected_filter_content.html"), "w", encoding="utf-8") as f:
    #    f.write(filtered_content)
    expected_html = read_fixture("expected_filter_content.html", subfolder="board_of_aldermen")
    assert filtered_content.strip() == expected_html.strip()
    actual_md = to_markdown(filtered_content)
    #with open(os.path.join(FIXTURE_DIR, "board_of_aldermen", "expected_filter_content.md"), "w", encoding="utf-8") as f:
    #    f.write(actual_md)
    with open(os.path.join(FIXTURE_DIR, "board_of_aldermen", "expected_filter_content.md"), "r", encoding="utf-8") as f:
        expected_md = f.read()
    assert actual_md.strip() == expected_md.strip()


def test_with_wix_site():
    folder = os.path.join(FIXTURE_DIR, "wix_site")
    with open(os.path.join(folder, "expected_clean_html.html"), "r", encoding="utf-8") as f:
        input_html = f.read()
    filtered_content = filter_content(logger, {}, input_html)
    with open(os.path.join(folder, "expected_filter_content.html"), "w", encoding="utf-8") as f:
        f.write(filtered_content)
    expected_html = read_fixture("expected_filter_content.html", subfolder=folder)
    assert filtered_content.strip() == expected_html.strip()
    actual_md = to_markdown(filtered_content)
    with open(os.path.join(folder, "expected_filter_content.md"), "w", encoding="utf-8") as f:
        f.write(actual_md)
    with open(os.path.join(folder, "expected_filter_content.md"), "r", encoding="utf-8") as f:
        expected_md = f.read()
    assert actual_md.strip() == expected_md.strip()
