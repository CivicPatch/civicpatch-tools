import sys
from typing import List

# TODO: should be more generic
from domain.models import Official
from shared.utils import data_path_utils


def generate_data_comment(data: List[Official]) -> str:
    """
    Generate a Markdown table from a list of Person objects.
    """
    table_header = (
        "| **Name**  | **Office Name**  | **Division**  | **Emails**     | **Phones**     | **Urls**      | **Term Dates** | **Image**     | ** Source URLs **|\n"
        "|-----------|------------------|---------------|----------------|----------------|---------------|----------------|---------------|------------------|\n"
    )
    table_rows = ""

    def format_url(url: str) -> str:
        return f"[Link]({url})" if url else "N/A"

    for person in data:
        name = person.name
        office_name = person.office.name if person.office.name else "N/A"
        divisions = person.office.division_ocdid if person.office.division_ocdid else "N/A"
        emails = person.emails if person.emails else "N/A"
        phones = person.phones if person.phones else "N/A"
        urls = ", ".join(format_url(url) for url in person.urls) if person.urls else "N/A"
        term_dates = f"{person.start_date or 'N/A'} - {person.end_date or 'N/A'}"
        image = f"![image of {person.name}]({person.image})" if person.image else "N/A"
        source_urls = to_markdown_list(person.source_urls)

        table_rows += f"| **{name}** | {office_name} | {divisions} | {emails} | {phones} | {urls} | {term_dates} | {image} | {source_urls} |\n"

    return table_header + table_rows

def to_markdown_list(items: List[str]) -> str:
    """
    Convert a list of strings to a Markdown-formatted list.
    """
    if not items:
        return "N/A"
    return "\n".join(f"- {item}" for item in items)


def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_data_comment.py <jurisdiction_ocdid>")
        sys.exit(1)

    jurisdiction_ocdid = sys.argv[1]
    try:
        # It should be defined in the dockerfile
        serialized_people = data_path_utils.get_data(
            jurisdiction_ocdid
        )
        people = [Official(**person) for person in serialized_people]
        markdown_table = generate_data_comment(people)
        print(markdown_table)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
