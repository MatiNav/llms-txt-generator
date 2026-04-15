import logging
from urllib.parse import urlparse

from handlers.lambdas.processing.pipeline.optional_filter import (
    build_optional_description,
    filter_optionals,
)
from shared.logging import log_decision
from shared.pipeline.processing_types import (
    OptionalCandidate,
    OptionalEntry,
    OptionalDecision,
    ProcessedPage,
    RootDocumentIR,
    SectionDocumentIR,
    SectionGroup,
)
from shared.pipeline.summary_placeholders import (
    root_details_placeholder,
    root_summary_placeholder,
    section_summary_placeholder,
)


logger = logging.getLogger(__name__)


def build_document_ir(
    section_groups: list[SectionGroup],
    *,
    decision_context: dict[str, str] | None = None,
) -> RootDocumentIR:
    context_fields = decision_context or {}
    section_documents: list[SectionDocumentIR] = []
    core_urls: set[str] = set()
    optional_candidates: list[OptionalCandidate] = []

    for section_group in section_groups:
        core_urls.update(
            grouped_page.normalized_url for grouped_page in section_group.pages
        )
        optional_candidates.extend(_collect_optional_candidates(section_group.pages))

        section_documents.append(
            SectionDocumentIR(
                section_key=section_group.section_key,
                section_title=section_group.section_title,
                summary_placeholder=section_summary_placeholder(
                    section_group.section_key
                ),
                pages=section_group.pages,
            )
        )

        log_decision(
            logger,
            decision_name="ir.section_document_created",
            reason="section group transformed into section document with stable placeholders",
            section_key=section_group.section_key,
            section_title=section_group.section_title,
            page_count=len(section_group.pages),
            **context_fields,
        )

    filtered_optional_candidates = filter_optionals(
        optional_candidates,
        core_urls,
        decision_context=context_fields,
    )
    optional_entries = _build_optional_entries(filtered_optional_candidates)

    root_document = RootDocumentIR(
        root_title=_derive_root_title(section_groups),
        root_summary_placeholder=root_summary_placeholder(),
        root_details_placeholder=root_details_placeholder(),
        sections=section_documents,
        optional_entries=optional_entries,
    )

    log_decision(
        logger,
        decision_name="ir.root_document_created",
        reason="all sections assembled under root document",
        section_count=len(section_documents),
        optional_candidate_count=len(optional_candidates),
        optional_entry_count=len(optional_entries),
        **context_fields,
    )

    return root_document


def _collect_optional_candidates(
    section_pages: list[ProcessedPage],
) -> list[OptionalCandidate]:
    homepage_resource_pages = [
        section_page
        for section_page in section_pages
        if _is_homepage_like(section_page.url)
    ]
    if not homepage_resource_pages:
        return []

    optional_candidates: list[OptionalCandidate] = []
    for source_page in homepage_resource_pages:
        source_kind = _resource_source_kind(source_page.url)
        source_context = source_page.title or source_page.h1

        for external_url in sorted(source_page.external_links):
            optional_candidates.append(
                OptionalCandidate(
                    url=external_url,
                    anchor_text=None,
                    source_url=source_page.url,
                    source_kind=source_kind,
                    raw_context=source_context,
                )
            )

        for mailto_url in sorted(source_page.mailto_links):
            optional_candidates.append(
                OptionalCandidate(
                    url=mailto_url,
                    anchor_text=None,
                    source_url=source_page.url,
                    source_kind=source_kind,
                    raw_context=source_context,
                )
            )

    return optional_candidates


def _build_optional_entries(
    filtered_candidates: list[tuple[OptionalCandidate, OptionalDecision]],
) -> list[OptionalEntry]:
    return [
        OptionalEntry(
            title=_build_optional_title(optional_candidate),
            url=optional_candidate.url,
            description=build_optional_description(
                optional_decision, optional_candidate
            ),
        )
        for optional_candidate, optional_decision in filtered_candidates
    ]


def _build_optional_title(optional_candidate: OptionalCandidate) -> str:
    anchor_title = (optional_candidate.anchor_text or "").strip()
    if anchor_title:
        return anchor_title

    optional_url = optional_candidate.url
    if optional_url.startswith("mailto:"):
        email_address = optional_url[len("mailto:") :].split("?", 1)[0]
        return f"Email {email_address}"

    parsed_url = urlparse(optional_url)
    hostname = parsed_url.hostname or optional_url
    path_component = parsed_url.path.rstrip("/")
    if not path_component or path_component == "/":
        return hostname
    return f"{hostname}{path_component}"


def _is_homepage_like(page_url: str) -> bool:
    parsed_url = urlparse(page_url)
    normalized_path = parsed_url.path.rstrip("/")
    return normalized_path == ""


def _resource_source_kind(source_url: str) -> str:
    if _is_homepage_like(source_url):
        return "homepage"
    return "root_page"


def _derive_root_title(section_groups: list[SectionGroup]) -> str:
    all_pages: list[ProcessedPage] = []
    for section_group in section_groups:
        all_pages.extend(section_group.pages)

    if not all_pages:
        return "llms.txt"

    sorted_pages = sorted(
        all_pages,
        key=lambda processed_page: (
            processed_page.depth,
            processed_page.normalized_url,
        ),
    )
    homepage_candidate = sorted_pages[0]
    return homepage_candidate.title or homepage_candidate.h1 or homepage_candidate.url
