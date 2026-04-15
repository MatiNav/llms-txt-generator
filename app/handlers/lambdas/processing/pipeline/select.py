import logging

from shared.logging import log_decision
from shared.pipeline.processing_types import ProcessedPage


logger = logging.getLogger(__name__)


def select_eligible_pages(
    processed_pages: list[ProcessedPage],
    *,
    decision_context: dict[str, str] | None = None,
) -> list[ProcessedPage]:
    context_fields = decision_context or {}
    deduplicated_by_url: dict[str, ProcessedPage] = {}

    sorted_pages = sorted(
        processed_pages,
        key=lambda processed_page: (
            processed_page.depth,
            processed_page.normalized_url,
            processed_page.url,
        ),
    )
    for processed_page in sorted_pages:
        existing_page = deduplicated_by_url.get(processed_page.normalized_url)
        if existing_page is None:
            deduplicated_by_url[processed_page.normalized_url] = processed_page
            continue

        log_decision(
            logger,
            decision_name="selection.duplicate_canonical_url_skipped",
            reason="normalized_url already selected at a better or equal deterministic rank",
            kept_run_page_id=existing_page.run_page_id,
            skipped_run_page_id=processed_page.run_page_id,
            normalized_url=processed_page.normalized_url,
            **context_fields,
        )

    eligible_pages: list[ProcessedPage] = []
    for normalized_url in sorted(deduplicated_by_url.keys()):
        page_candidate = deduplicated_by_url[normalized_url]
        is_eligible, ineligible_reason = _eligibility_result(page_candidate)
        if is_eligible:
            eligible_pages.append(page_candidate)
            continue

        log_decision(
            logger,
            decision_name="selection.page_rejected",
            reason=ineligible_reason,
            run_page_id=page_candidate.run_page_id,
            normalized_url=page_candidate.normalized_url,
            content_length=page_candidate.content_length,
            has_title=bool(page_candidate.title),
            has_h1=bool(page_candidate.h1),
            has_meta_description=bool(page_candidate.meta_description),
            has_og_description=bool(page_candidate.og_description),
            **context_fields,
        )

    log_decision(
        logger,
        decision_name="selection.completed",
        reason="eligible pages computed using deterministic deduplication and quality gates",
        input_page_count=len(processed_pages),
        canonical_page_count=len(deduplicated_by_url),
        eligible_page_count=len(eligible_pages),
        rejected_page_count=max(len(deduplicated_by_url) - len(eligible_pages), 0),
        **context_fields,
    )

    return eligible_pages


def _eligibility_result(processed_page: ProcessedPage) -> tuple[bool, str]:
    if processed_page.content_length <= 0:
        return False, "content_length is zero"

    if not (
        processed_page.title
        or processed_page.h1
        or processed_page.meta_description
        or processed_page.og_description
    ):
        return False, "page has no title, h1, meta_description, or og_description"

    return True, "page passed selection gates"
