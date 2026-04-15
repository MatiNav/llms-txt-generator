from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.constants.run_state import (
    RUN_STATE_COMPLETED,
    RUN_STATE_FAILED,
    RUN_STATE_READY_FOR_LLM_GENERATION,
)
from shared.models import Run, RunPage


@dataclass(frozen=True)
class LlmGenerationRunContext:
    run_id: str
    site_id: str
    state: str


@dataclass(frozen=True)
class PageSummaryContext:
    url: str
    title: str | None
    meta_description: str | None
    og_description: str | None
    h1: str | None
    content_length: int | None


class LlmGeneratorRepository:
    def __init__(self, database_session: AsyncSession) -> None:
        self.database_session = database_session

    async def get_run_context(self, run_id: str) -> LlmGenerationRunContext | None:
        statement = (
            select(Run.id, Run.site_id, Run.state).where(Run.id == run_id).limit(1)
        )
        row = (await self.database_session.execute(statement)).first()
        if row is None:
            return None

        return LlmGenerationRunContext(
            run_id=str(row[0]),
            site_id=str(row[1]),
            state=str(row[2]),
        )

    async def get_page_context_by_url(
        self, run_id: str
    ) -> dict[str, PageSummaryContext]:
        statement = select(RunPage.url, RunPage.metadata_json).where(
            RunPage.run_id == run_id
        )
        rows = (await self.database_session.execute(statement)).all()

        context_by_url: dict[str, PageSummaryContext] = {}
        for row in rows:
            page_url = str(row[0])
            metadata_json = row[1] if isinstance(row[1], dict) else {}
            context_by_url[page_url] = PageSummaryContext(
                url=page_url,
                title=_read_optional_text(metadata_json, "title"),
                meta_description=_read_optional_text(metadata_json, "meta_description"),
                og_description=_read_optional_text(metadata_json, "og_description"),
                h1=_read_optional_text(metadata_json, "h1"),
                content_length=_read_optional_int(metadata_json, "content_length"),
            )

        return context_by_url

    async def mark_run_completed(self, run_id: str) -> bool:
        statement = (
            update(Run)
            .where(Run.id == run_id)
            .where(Run.state == RUN_STATE_READY_FOR_LLM_GENERATION)
            .values(
                state=RUN_STATE_COMPLETED,
                completed_at=func.now(),
                error_message=None,
            )
            .returning(Run.id)
        )
        result = await self.database_session.execute(statement)
        return result.first() is not None

    async def mark_run_failed(self, *, run_id: str, error_message: str) -> bool:
        statement = (
            update(Run)
            .where(Run.id == run_id)
            .where(Run.state == RUN_STATE_READY_FOR_LLM_GENERATION)
            .values(
                state=RUN_STATE_FAILED,
                error_message=error_message[:1000],
                completed_at=func.now(),
            )
            .returning(Run.id)
        )
        result = await self.database_session.execute(statement)
        return result.first() is not None

    @staticmethod
    def is_terminal_state(run_state: str) -> bool:
        return run_state in {RUN_STATE_COMPLETED, RUN_STATE_FAILED}


def _read_optional_text(metadata_json: dict, key_name: str) -> str | None:
    raw_value = metadata_json.get(key_name)
    if not isinstance(raw_value, str):
        return None
    normalized_value = raw_value.strip()
    return normalized_value if normalized_value else None


def _read_optional_int(metadata_json: dict, key_name: str) -> int | None:
    raw_value = metadata_json.get(key_name)
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int):
        return raw_value
    return None
