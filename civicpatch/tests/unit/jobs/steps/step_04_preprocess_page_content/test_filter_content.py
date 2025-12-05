import os
import difflib
from jobs.people_collector.steps.step_04_preprocess_page_content.filter_content import filter_content
from markdownify import markdownify as md

def read_fixture(filename, subfolder="with_table"):
    fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", subfolder)
    with open(os.path.join(fixture_dir, filename), "r", encoding="utf-8") as f:
        return f.read().strip()

def assert_markdown_equal(actual_html, expected_md, government_type, subfolder="with_table"):
    print("asserting...")
    actual_html = filter_content(actual_html, government_type)
    actual_md = md(actual_html).strip()
    expected_md = expected_md.strip()
    actual_lines = actual_md.splitlines()
    expected_lines = expected_md.splitlines()
    if actual_lines != expected_lines:
        print("\n".join(difflib.unified_diff(expected_lines, actual_lines, fromfile="expected", tofile="actual", lineterm="")))
        fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", subfolder)
        output_path = os.path.join(fixture_dir, "actual_preprocessed.md")
        output_html_path = os.path.join(fixture_dir, "actual_preprocessed.html")
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(actual_html)
        print(f"Actual HTML output written to {output_html_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(actual_md)
        print(f"Actual preprocessed output written to {output_path}")
    assert actual_lines == expected_lines

 #def test_filter_content_with_real_data():
 #    original = read_fixture("original.html")
 #    expected = read_fixture("preprocessed.md")
 #    assert original, "Original fixture is missing or empty"
 #    assert_markdown_equal(original, expected, government_type="mayor_council")

def test_filter_content_with_seattle():
    original = read_fixture("original.html", subfolder="seattle_council")
    expected = read_fixture("preprocessed.md", subfolder="seattle_council")
    assert original, "Keyword test fixture is missing or empty"
    assert_markdown_equal(original, expected, "mayor_council", subfolder="seattle_council")


#def test_filter_content_with_big_page():
#    original = read_fixture("original.html", subfolder="big_page")
#    expected = read_fixture("preprocessed.md", subfolder="big_page")
#    assert original, "Big page test fixture is missing or empty"
#    assert_markdown_equal(original, expected, "mayor_council", subfolder="big_page")

# def test_filter_content_with_table():
#     original = read_fixture("original.html", subfolder="with_table")
#     expected = read_fixture("preprocessed.md", subfolder="with_table")
#     assert original, "Table test fixture is missing or empty"
#     assert_markdown_equal(original, expected, "mayor_council", subfolder="with_table")