from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class Office(BaseModel):
    name: str
    division_id: Optional[str] = None
 
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class Official(BaseModel):
    name: str
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []

    office: Office = None

    image: Optional[str] = None

    jurisdiction_id: str
    cdn_image: Optional[str] = None
    source_urls: List[str]  
    updated_at: str

class Person(BaseModel):
    name: str
    # address: NOTE: not implemented, we are NOT collecting addresses
    roles: List[str] = []
    divisions: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None

    jurisdiction_id: str 
    cdn_image: Optional[str] = None
    source_urls: List[str] 
    updated_at: str

def person_to_official(person: Person) -> Official:
    return Official(
        name=person.name,

        phones=person.phones,
        emails=person.emails,
        urls=person.urls,

        office=Office(
            name=" - ".join(person.roles),
            division_id=person.divisions[0] if person.divisions else None,
            start_date=person.start_date,
            end_date=person.end_date,
        ),
        
        image=person.image,

        jurisdiction_id=person.jurisdiction_id,
        cdn_image=person.cdn_image,
        source_urls=person.source_urls,
        updated_at=person.updated_at,
    )
