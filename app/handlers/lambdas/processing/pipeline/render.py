import logging

from shared.logging import log_decision
from shared.pipeline.processing_types import (
    OptionalEntry,
    RenderedFile,
    RootDocumentIR,
    SectionDocumentIR,
)
from shared.pipeline.summary_placeholders import section_short_summary_placeholder


logger = logging.getLogger(__name__)


def render_documents(
    root_document: RootDocumentIR,
    *,
    decision_context: dict[str, str] | None = None,
) -> list[RenderedFile]:
    context_fields = decision_context or {}
    rendered_files: list[RenderedFile] = []
    rendered_files.append(_render_root_file(root_document))

    for section_document in root_document.sections:
        rendered_files.append(_render_section_file(section_document))

    log_decision(
        logger,
        decision_name="render.completed",
        reason="root and section llms files rendered with summary placeholders",
        section_count=len(root_document.sections),
        rendered_file_count=len(rendered_files),
        rendered_relative_paths=[
            rendered_file.relative_path for rendered_file in rendered_files
        ],
        **context_fields,
    )

    return rendered_files


def infer_output_mode(
    rendered_files: list[RenderedFile],
    *,
    decision_context: dict[str, str] | None = None,
) -> str:
    context_fields = decision_context or {}
    has_leaf_documents = any(
        rendered_file.relative_path != "llms.txt" for rendered_file in rendered_files
    )
    output_mode = "hierarchical" if has_leaf_documents else "single_file"

    log_decision(
        logger,
        decision_name="render.output_mode_inferred",
        reason=(
            "at least one non-root rendered file exists"
            if has_leaf_documents
            else "only root llms.txt exists"
        ),
        output_mode=output_mode,
        rendered_file_count=len(rendered_files),
        **context_fields,
    )

    return output_mode


def _render_root_file(root_document: RootDocumentIR) -> RenderedFile:
    lines: list[str] = [
        f"# {root_document.root_title}",
        "",
        f"> {root_document.root_summary_placeholder}",
        "",
        root_document.root_details_placeholder,
        "",
    ]

    for section_document in root_document.sections:
        section_file_path = _section_relative_path(section_document.section_key)
        lines.extend(
            [
                f"## {section_document.section_title}",
                "",
                (
                    f"- [{section_document.section_title}]({section_file_path}): "
                    f"{section_short_summary_placeholder(section_document.section_key)}"
                ),
                "",
            ]
        )

    if root_document.optional_entries:
        lines.extend(["## Optional", ""])
        for optional_entry in root_document.optional_entries:
            lines.append(_render_optional_entry(optional_entry))
        lines.append("")

    return RenderedFile(
        relative_path="llms.txt", content="\n".join(lines).strip() + "\n"
    )


def _render_section_file(section_document: SectionDocumentIR) -> RenderedFile:
    lines: list[str] = [
        f"# {section_document.section_title}",
        "",
        section_document.summary_placeholder,
        section_short_summary_placeholder(section_document.section_key),
        "",
    ]

    for processed_page in section_document.pages:
        page_title = processed_page.title or processed_page.h1 or processed_page.url
        page_description = (
            processed_page.meta_description
            or processed_page.og_description
            or "Description unavailable"
        )
        lines.append(f"- [{page_title}]({processed_page.url}): {page_description}")

    return RenderedFile(
        relative_path=_section_relative_path(section_document.section_key),
        content="\n".join(lines).strip() + "\n",
    )


def _section_relative_path(section_key: str) -> str:
    return f"{section_key}/llms.txt"


def _render_optional_entry(optional_entry: OptionalEntry) -> str:
    return f"- [{optional_entry.title}]({optional_entry.url})"
