import logging
from urllib.parse import urlparse

from shared.logging import log_decision
from shared.pipeline.processing_types import ProcessedPage, SectionGroup


logger = logging.getLogger(__name__)


def group_pages_by_section(
    eligible_pages: list[ProcessedPage],
    *,
    decision_context: dict[str, str] | None = None,
) -> list[SectionGroup]:
    context_fields = decision_context or {}
    grouped_pages: dict[str, list[ProcessedPage]] = {}
    section_titles: dict[str, str] = {}

    for eligible_page in eligible_pages:
        section_key, section_title, grouping_reason = _derive_section_for_page(
            eligible_page
        )
        grouped_pages.setdefault(section_key, []).append(eligible_page)
        section_titles[section_key] = section_title
        log_decision(
            logger,
            decision_name="grouping.page_assigned_to_section",
            reason=grouping_reason,
            run_page_id=eligible_page.run_page_id,
            normalized_url=eligible_page.normalized_url,
            section_key=section_key,
            section_title=section_title,
            **context_fields,
        )

    section_groups: list[SectionGroup] = []
    for section_key in sorted(grouped_pages.keys()):
        pages_in_section = sorted(
            grouped_pages[section_key],
            key=lambda page_item: (page_item.depth, page_item.normalized_url),
        )
        section_groups.append(
            SectionGroup(
                section_key=section_key,
                section_title=section_titles[section_key],
                pages=pages_in_section,
            )
        )

    log_decision(
        logger,
        decision_name="grouping.completed",
        reason="eligible pages grouped by breadcrumb-first, then first path segment, then root fallback",
        eligible_page_count=len(eligible_pages),
        section_count=len(section_groups),
        section_keys=[section_group.section_key for section_group in section_groups],
        **context_fields,
    )

    return section_groups


def _derive_section_for_page(page: ProcessedPage) -> tuple[str, str, str]:
    if page.breadcrumbs:
        breadcrumb_value = page.breadcrumbs[0].strip()
        if breadcrumb_value:
            section_key = _sanitize_section_key(breadcrumb_value)
            return section_key, breadcrumb_value, "used first breadcrumb label"

    parsed_url = urlparse(page.url)
    path_segments = [segment for segment in parsed_url.path.split("/") if segment]
    if path_segments:
        first_segment = path_segments[0]
        section_key = _sanitize_section_key(first_segment)
        section_title = first_segment.replace("-", " ").replace("_", " ").title()
        return section_key, section_title, "used first URL path segment"

    return "root", "General", "no breadcrumb and no path segment available"


def _sanitize_section_key(raw_value: str) -> str:
    cleaned_value = raw_value.strip().lower().replace(" ", "-")
    sanitized_characters: list[str] = []
    for character in cleaned_value:
        if character.isalnum() or character in {"-", "_"}:
            sanitized_characters.append(character)

    normalized_value = "".join(sanitized_characters).strip("-")
    return normalized_value or "root"
