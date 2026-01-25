from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class Office(BaseModel):
    name: str
    division_ocdid: Optional[str] = None
 
class Official(BaseModel):
    name: str
    other_names: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    office: Office = None

    image: Optional[str] = None

    jurisdiction_ocdid: str
    cdn_image: Optional[str] = None
    source_urls: List[str]  
    updated_at: str

class Person(BaseModel):
    name: str
    # address: NOTE: not implemented, we are NOT collecting addresses
    other_names: List[str] = []
    roles: List[str] = []
    divisions: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None

    jurisdiction_ocdid: str 
    cdn_image: Optional[str] = None
    source_urls: List[str] 
    updated_at: str

def person_to_official(person: Person) -> Official:
    return Official(
        name=person.name,
        other_names=person.other_names,

        phones=person.phones,
        emails=person.emails,
        urls=person.urls,
        start_date=person.start_date or None,
        end_date=person.end_date or None,

        office=Office(
            name=" - ".join(person.roles),
            division_ocdid=person.divisions[0] if person.divisions else None,
        ),

        image=person.image or None,

        jurisdiction_ocdid=person.jurisdiction_ocdid,
        cdn_image=person.cdn_image or None,
        source_urls=person.source_urls,
        updated_at=person.updated_at,
    )
