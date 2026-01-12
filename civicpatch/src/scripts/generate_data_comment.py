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
        "| **Name**  | **Office Name**  | **Division**  | **Emails**     | **Phones**     | **Urls**      | **Term Dates** | **Image**     |\n"
        "|-----------|------------------|---------------|----------------|----------------|---------------|----------------|---------------|\n"
    )
    table_rows = ""

    def format_url(url: str) -> str:
        return f"[Link]({url})" if url else "N/A"

    for person in people:
        name = person.name
        office_name = person.office.name if person.office.name else "N/A"
        divisions = person.office.division_id if person.office.division_id else "N/A"
        emails = person.emails if person.emails else "N/A"
        phones = person.phones if person.phones else "N/A"
        urls = ", ".join(format_url(url) for url in person.urls) if person.urls else "N/A"
        term_dates = f"{person.office.start_date or 'N/A'} - {person.office.end_date or 'N/A'}"
        image = f"![]({person.cdn_image})" if person.cdn_image else "N/A"

        table_rows += f"| **{name}** | {office_name} | {divisions} | {emails} | {phones} | {urls} | {term_dates} | {image} |\n"

    return table_header + table_rows


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
