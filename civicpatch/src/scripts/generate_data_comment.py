import os
import yaml
import sys
from typing import List
from schemas import Person

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

def load_people_from_yaml(filepath: str) -> List[Person]:
    """
    Load a list of Person objects from a YAML file.
    """
    with open(filepath, "r") as file:
        data = yaml.safe_load(file)
        return [Person(**person_data) for person_data in data]

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_data_comment.py <municipality_path>")
        sys.exit(1)
    
    municipality_path = sys.argv[1]
    try:
        # It should be defined in the dockerfile
        PYTHONPATH = os.getenv("PYTHONPATH", "/app/src")
        people_path = os.path.join(PYTHONPATH, "..", "data", municipality_path, "people.yml")
        people = load_people_from_yaml(people_path)
        markdown_table = generate_data_comment(people)
        print(markdown_table)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()