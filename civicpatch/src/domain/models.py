from pydantic import BaseModel
from typing import List, Optional, Tuple
from enum import Enum
from shared.utils.config_utils import get_designations

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
    designations: List[str] = []
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
    designation_configs = get_designations()
    role_designations, division_ocdid = extract_role_names_and_division_from_designations(
        designation_configs=designation_configs,
        jurisdiction_ocdid=person.jurisdiction_ocdid,
        office_designations=person.designations
    )
    office_names = person.roles + role_designations
    office_name = " - ".join(office_names) if office_names else "Unknown Office"
    return Official(
        name=person.name,
        other_names=person.other_names,

        phones=person.phones,
        emails=person.emails,
        urls=person.urls,
        start_date=person.start_date or None,
        end_date=person.end_date or None,

        office=Office(
            name=office_name,
            division_ocdid=division_ocdid
        ),

        image=person.image or None,

        jurisdiction_ocdid=person.jurisdiction_ocdid,
        cdn_image=person.cdn_image or None,
        source_urls=person.source_urls,
        updated_at=person.updated_at,
    )

def jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid: str) -> str:
    without_classification = jurisdiction_ocdid.rsplit('/', 1)[0]
    return without_classification.replace("ocd-jurisdiction", "ocd-division")

def extract_role_names_and_division_from_designations(designation_configs, jurisdiction_ocdid: str, office_designations: List[str]) -> Tuple[List[str], str]:
    role_names = []
    division = None
    division_base = jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid)

    # Any division that has a geographic area gets to set the division
    # Otherwise, division remains the base jurisdiction_ocdid
    for designation_string in office_designations:
        parts = designation_string.lower().split(' ')
        designation_key = parts[0]
        designation_value = ' '.join(parts[1:]).strip()
        if designation_key in designation_configs:
            config = designation_configs[designation_key]
            role_names.append(designation_string)

            if config.get("has_geographic_area", False) and designation_value:
                division = format_division(division_base, designation_key, designation_value)
    
    if division is None:
        division = division_base
        
    return role_names, division

def format_division(division_base: str, designation_key: str, designation_value: str) -> str:
    return f"{division_base}/{designation_key}:{designation_value}"