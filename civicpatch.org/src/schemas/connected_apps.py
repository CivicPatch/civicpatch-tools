from pydantic import BaseModel


class ConnectedApp(BaseModel):
    """An app (e.g. ChatGPT) the user approved through the OAuth consent page."""

    client_id: str
    name: str
    granted_at: str
