import logging

from shared.logging import log_decision
from shared.pipeline.processing_types import (
    RootDocumentIR,
    SectionDocumentIR,
    SectionGroup,
)
from shared.pipeline.summary_placeholders import (
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
    for section_group in section_groups:
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

    root_document = RootDocumentIR(
        root_summary_placeholder=root_summary_placeholder(),
        sections=section_documents,
    )

    log_decision(
        logger,
        decision_name="ir.root_document_created",
        reason="all sections assembled under root document",
        section_count=len(section_documents),
        **context_fields,
    )

    return root_document
