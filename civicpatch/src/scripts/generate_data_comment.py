import sys
from typing import List

from schemas import Person
from shared.utils import data_path_utils


def generate_data_comment(people: List[Person]) -> str:
    """
    Generate a Markdown table from a list of Person objects.
    """
    table_header = (
        "| **Name**  | **Roles**  | **Divisions** | **Email**     | **Phone**     | **Website**   | **Term Dates** | **Image**     |\n"
        "|-----------|------------|---------------|---------------|---------------|---------------|----------------|---------------|\n"
    )
    table_rows = ""
    for person in people:
        name = person.name
        roles = ", ".join(person.roles) if person.roles else "N/A"
        divisions = ", ".join(person.divisions) if person.divisions else "N/A"
        email = person.email if person.email else "N/A"
        phone = person.phone_number if person.phone_number else "N/A"
        website = f"[Link]({person.website})" if person.website else "N/A"
        term_dates = f"{person.start_date or 'N/A'} - {person.end_date or 'N/A'}"
        image = f"![]({person.cdn_image})" if person.cdn_image else "N/A"

        table_rows += f"| **{name}** | {roles} | {divisions} | {email} | {phone} | {website} | {term_dates} | {image} |\n"

    return table_header + table_rows


def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_data_comment.py <jurisdiction_id>")
        sys.exit(1)

    jurisdiction_id = sys.argv[1]
    try:
        # It should be defined in the dockerfile
        serialized_people = data_path_utils.get_data(
            jurisdiction_id
        )
        people = [Person(**person) for person in serialized_people]
        markdown_table = generate_data_comment(people)
        print(markdown_table)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
