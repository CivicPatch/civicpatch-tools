def find_person_by_name(people, name):
    for person in people:
        if person.name == name:
            return person
    return None