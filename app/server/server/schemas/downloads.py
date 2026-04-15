from uuid import UUID

from pydantic import BaseModel


class RunDownloadsResponse(BaseModel):
    run_id: UUID
    bundle_zip_url: str
    expires_in_seconds: int
