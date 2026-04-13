from uuid import UUID

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class GenerateResponse(BaseModel):
    run_id: UUID
    site_id: UUID
    state: str
    coalesced: bool
