from typing import List

from pydantic import BaseModel, Field


class JurisdictionsByOcdidsRequest(BaseModel):
    ocdids: List[str]


class JurisdictionSearchResult(BaseModel):
    jurisdiction_ocdid: str
    level: str
    # Display names of the row's parent_ocdids, most specific first — e.g.
    # ["King County", "Washington"]. The ocdid carries only slugs, and a slug's display
    # name lives on the parent's own row, so this cannot be derived client-side.
    # Empty where open-data records no parents (all of NC and TN, some of MI/NJ).
    parent_names: list[str] = []
    # Official name, Census type suffix intact ("Albion township"). The suffix
    # disambiguates — MI has an Albion city and an Albion township.
    name: str
    # Friendly form ("Albion"). Absent until open-data emits it; callers fall back.
    display_name: str | None = None
    population: int | None = None


class PaginationLinks(BaseModel):
    # "self" is unusable as an attribute name, so serialize under the alias. FastAPI
    # dumps response models by alias, matching the envelope /{state}/search returns.
    prev: str = ""
    next: str = ""
    self_link: str = Field("", alias="self")


class JurisdictionSearchResponse(BaseModel):
    total_items: int
    page: int
    total_pages: int
    limit: int
    data: list[JurisdictionSearchResult]
    links: PaginationLinks
