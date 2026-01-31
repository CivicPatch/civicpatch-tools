from domain.models import Person

def person_factory(
        name,
        other_names=[],
        phones=[],
        emails=[],
        urls=[],
        roles=["Council Member"],
        designations=[],
        source_urls=["https://example.gov"],
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government"
) -> Person:
   return Person(
        name=name,
        other_names=other_names,
        roles=roles,
        designations=designations,
        phones=phones,
        emails=emails,
        urls=urls,

        start_date=None,
        end_date=None,
        image=None,

        jurisdiction_ocdid=jurisdiction_ocdid,
        cdn_image=None,
        source_urls=source_urls,
        updated_at=""
    )