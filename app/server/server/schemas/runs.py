from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RunStatusResponse(BaseModel):
    run_id: UUID
    site_id: UUID
    site_root_url: str
    state: str
    stage: str
    pages_detected: int
    pages_queued: int
    pages_completed: int
    completed_reason: str | None
    error_message: str | None
    updated_at: datetime
