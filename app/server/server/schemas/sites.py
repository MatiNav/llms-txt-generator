from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SiteResponse(BaseModel):
    site_id: UUID
    root_url: str
    created_at: datetime
