from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from orchestrator.adapters.strategy_probe_adapter import detect_strategy
from orchestrator.config import DISCOVERING_STATE
from orchestrator.message_types import ReservationOutcome
from shared.db.session import get_db_session
from shared.models import Run, RunPage
from shared.pipeline.url_norm import canonical_url


async def reserve_run_page_and_increment_pages_queued(
    run_id: str,
    page_url: str,
    page_depth: int,
) -> tuple[ReservationOutcome, str | None, list[str] | None]:
    async with get_db_session() as database_session:
        run_statement = select(Run).where(Run.id == run_id)
        run_result = await database_session.execute(run_statement)
        run = run_result.scalar_one_or_none()

        if run is None:
            return "run_missing", None, None
        if run.state != DISCOVERING_STATE:
            return "run_not_discovering", run.strategy, None

        normalized_page_url = canonical_url(page_url)
        insert_statement = (
            postgres_insert(RunPage)
            .values(
                run_id=run_id,
                url=page_url,
                normalized_url=normalized_page_url,
                depth=page_depth,
                fetch_status="queued",
                page_status="NEW",
            )
            .on_conflict_do_nothing(constraint="uq_run_page_url")
        )
        insert_result = await database_session.execute(insert_statement)

        if insert_result.rowcount == 0:
            return "deduplicated", run.strategy, None

        strategy_reason_markers: list[str] | None = None
        if run.strategy is None:
            detected_strategy, strategy_reason_markers = await detect_strategy(page_url)
            run.strategy = detected_strategy

        run.pages_queued += 1
        return "inserted", run.strategy, strategy_reason_markers
