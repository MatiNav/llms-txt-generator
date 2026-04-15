import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.config import SERVICE_NAME
from shared.constants.page_status import PAGE_STATUS_UNCHANGED
from shared.constants.run_state import (
    RUN_STATE_COMPLETED,
    RUN_STATE_DISCOVERING,
    RUN_STATE_PROCESSING,
)
from shared.logging import log_event
from shared.models import Run, RunPage
from shared.pipeline.processing_message import build_processing_requested_message
from shared.queue.sns_client import SNSClient


logger = logging.getLogger(__name__)


async def _load_root_page_status(
    *,
    database_session: AsyncSession,
    run_id: str,
) -> str | None:
    root_status_statement = (
        select(RunPage.page_status)
        .where(RunPage.run_id == run_id)
        .where(RunPage.depth == 0)
        .order_by(RunPage.updated_at.desc())
        .limit(1)
    )
    root_status_result = await database_session.execute(root_status_statement)
    root_page_status = root_status_result.scalar_one_or_none()
    if root_page_status is None:
        return None
    return str(root_page_status)


async def _try_complete_unchanged_root_run(
    *,
    database_session: AsyncSession,
    run_id: str,
    site_id: str,
    page_id: str,
) -> bool:
    root_page_status = await _load_root_page_status(
        database_session=database_session,
        run_id=run_id,
    )
    if root_page_status != PAGE_STATUS_UNCHANGED:
        return False

    completion_statement = (
        update(Run)
        .where(Run.id == run_id)
        .where(Run.state == RUN_STATE_DISCOVERING)
        .where(Run.processing_enqueued_at.is_(None))
        .where(Run.pages_completed >= Run.pages_queued)
        .values(
            state=RUN_STATE_COMPLETED,
            completed_at=func.now(),
            error_message=None,
        )
        .returning(Run.id)
    )
    completion_result = await database_session.execute(completion_statement)
    completed_row = completion_result.first()
    if completed_row is None:
        return False

    await database_session.commit()
    log_event(
        logger,
        logging.INFO,
        "completion.short_circuit_root_unchanged",
        service=SERVICE_NAME,
        component="orchestrator",
        run_id=run_id,
        site_id=site_id,
        page_id=page_id,
    )
    return True


async def try_emit_processing_requested(
    *,
    database_session: AsyncSession,
    processing_topic_client: SNSClient,
    processing_topic_arn: str,
    run_id: str,
    site_id: str,
    page_id: str,
) -> bool:
    was_run_short_circuited = await _try_complete_unchanged_root_run(
        database_session=database_session,
        run_id=run_id,
        site_id=site_id,
        page_id=page_id,
    )
    if was_run_short_circuited:
        return True

    transition_statement = (
        update(Run)
        .where(Run.id == run_id)
        .where(Run.state == RUN_STATE_DISCOVERING)
        .where(Run.processing_enqueued_at.is_(None))
        .where(Run.pages_completed >= Run.pages_queued)
        .values(
            state=RUN_STATE_PROCESSING,
            processing_enqueued_at=func.now(),
        )
        .returning(Run.id)
    )

    transition_result = await database_session.execute(transition_statement)
    transitioned_row = transition_result.first()
    if transitioned_row is None:
        log_event(
            logger,
            logging.INFO,
            "completion.not_ready",
            service=SERVICE_NAME,
            component="orchestrator",
            run_id=run_id,
            site_id=site_id,
            page_id=page_id,
        )
        return False

    await database_session.commit()

    log_event(
        logger,
        logging.INFO,
        "completion.transitioned",
        service=SERVICE_NAME,
        component="orchestrator",
        run_id=run_id,
        site_id=site_id,
        page_id=page_id,
        new_state=RUN_STATE_PROCESSING,
    )

    try:
        message_id = await processing_topic_client.publish_message(
            topic_arn=processing_topic_arn,
            payload=build_processing_requested_message(
                run_id=run_id,
                site_id=site_id,
            ),
        )
    except Exception as publish_error:
        log_event(
            logger,
            logging.ERROR,
            "completion.publish_failed",
            service=SERVICE_NAME,
            component="orchestrator",
            run_id=run_id,
            site_id=site_id,
            page_id=page_id,
            topic_arn=processing_topic_arn,
            error_type=type(publish_error).__name__,
            error_message=str(publish_error)[:500],
        )
        raise

    log_event(
        logger,
        logging.INFO,
        "completion.published",
        service=SERVICE_NAME,
        component="orchestrator",
        run_id=run_id,
        site_id=site_id,
        page_id=page_id,
        topic_arn=processing_topic_arn,
        message_id=message_id,
    )
    return True
