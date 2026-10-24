from typing import Annotated

from pydantic import BaseModel, StringConstraints

from schemas.common import ApiKeyScope

MAX_LABEL_LENGTH = 100

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LABEL_LENGTH)]


class CreateApiKeyRequest(BaseModel):
    label: Label
    scope: ApiKeyScope = ApiKeyScope.AGENT
