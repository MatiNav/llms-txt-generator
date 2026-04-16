from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.constants.run_state import (
    RUN_STATE_COMPLETED,
    RUN_STATE_FAILED,
    RUN_STATE_READY_FOR_LLM_GENERATION,
)
from shared.models import Run


@dataclass(frozen=True)
class LlmGenerationRunContext:
    run_id: str
    site_id: str
    state: str


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
