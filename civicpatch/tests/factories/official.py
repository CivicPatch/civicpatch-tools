from domain.models import Official, Office

def official_factory(
        name,
        other_names=[],
        phones=[],
        emails=[],
        urls=[],
        roles=["Council Member"],
        divisions=[],
        source_urls=["https://example.gov"],
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government"
) -> Official:
   # hardcode for now...
   division_ocdid = "ocd-division/country:us/state:wa/place:seattle"
   return Official(
        name=name,
        other_names=other_names,
        phones=phones,
        emails=emails,
        urls=urls,
        start_date=None,
        end_date=None,
        office=Office(
            name=' - '.join(roles),
            division_ocdid=division_ocdid or jurisdiction_ocdid
        ),
        jurisdiction_ocdid=jurisdiction_ocdid,
        cdn_image=None,
        source_urls=source_urls,
        updated_at=""
    )