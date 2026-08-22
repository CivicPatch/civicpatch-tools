from shared.schemas import Person


def person_factory(
    name,
    other_names=[],
    phones=[],
    emails=[],
    urls=[],
    labels=["Council Member"],
    image=None,
    source_urls=["https://example.gov"],
    jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government",
) -> Person:
    return Person(
        name=name,
        other_names=other_names,
        labels=labels,
        phones=phones,
        emails=emails,
        urls=urls,
        start_date=None,
        end_date=None,
        image=image,
        jurisdiction_ocdid=jurisdiction_ocdid,
        cdn_image=None,
        source_urls=source_urls,
        updated_at="2024-01-01T00:00:00+00:00",
    )
