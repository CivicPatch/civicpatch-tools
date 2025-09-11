import os
import difflib
from steps.step_04_preprocess_page_content.filter_content import filter_content
from markdownify import markdownify as md

def read_fixture(filename, subfolder="with_table"):
        fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", subfolder)
        with open(os.path.join(fixture_dir, filename), "r", encoding="utf-8") as f:
            return f.read().strip()

def write_diff_and_output(expected, actual, output_path):
    diff = difflib.unified_diff(
        expected,
        actual,
        fromfile='expected',
        tofile='actual',
        lineterm=''
    )
    for line in diff:
        print(line)
    print("```")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(actual))
    print(f"Actual preprocessed output written to {output_path}")

def test_filter_content_with_real_data():
    original = read_fixture("original.html")
    expected = read_fixture("preprocessed.md")
    assert original, "Original fixture is missing or empty"
    result_md = md(filter_content(original).strip()).strip()
    expected_md = expected.strip()
    result_lines = result_md.splitlines()
    expected_lines = expected_md.splitlines()
    if result_lines != expected_lines:
        fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", "with_table")
        output_path = os.path.join(fixture_dir, "actual_preprocessed.md")
        write_diff_and_output(expected_lines, result_lines, output_path)
    assert result_lines == expected_lines
