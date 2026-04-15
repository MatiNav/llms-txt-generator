from uuid import UUID

from pydantic import BaseModel


class RunDownloadsResponse(BaseModel):
    run_id: UUID
    llms_txt_url: str | None
    bundle_zip_url: str | None
    expires_in_seconds: int
