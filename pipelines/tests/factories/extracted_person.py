from runners.people_collector.schemas import ExtractedPersonRecord


def extracted_person_factory(name, label, **fields) -> ExtractedPersonRecord:
    return ExtractedPersonRecord(name=name, label=label, **fields)
