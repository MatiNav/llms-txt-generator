from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from shared.constants.render_mode import (
    ALLOWED_RENDER_MODES,
    RenderModeValue,
)


class GenerateRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    render_mode: RenderModeValue

    @field_validator("render_mode", mode="before")
    @classmethod
    def normalize_render_mode(cls, raw_value: str) -> str:
        normalized_render_mode = raw_value.strip().lower()
        if normalized_render_mode not in ALLOWED_RENDER_MODES:
            supported_modes_text = ", ".join(ALLOWED_RENDER_MODES)
            raise ValueError(f"render_mode must be one of: {supported_modes_text}")
        return normalized_render_mode


class GenerateResponse(BaseModel):
    run_id: UUID
    site_id: UUID
    state: str
    coalesced: bool
