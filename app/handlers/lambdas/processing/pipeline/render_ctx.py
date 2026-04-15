from html import escape

from shared.pipeline.processing_types import (
    RenderedFile,
    RootDocumentIR,
    SectionDocumentIR,
)


def render_ctx_documents(root_document: RootDocumentIR) -> list[RenderedFile]:
    concise_content = _render_ctx_file(root_document, include_optional=False)
    full_content = _render_ctx_file(root_document, include_optional=True)
    return [
        RenderedFile(relative_path="llms-ctx.txt", content=concise_content),
        RenderedFile(relative_path="llms-ctx-full.txt", content=full_content),
    ]


def _render_ctx_file(root_document: RootDocumentIR, *, include_optional: bool) -> str:
    mode = "ctx-full" if include_optional else "ctx"
    lines: list[str] = [
        f'<project title="{_escape_attr(root_document.root_title)}" mode="{mode}">',
        f"{_escape_text(root_document.root_summary_placeholder)}",
        "<docs>",
    ]

    for section_document in root_document.sections:
        lines.extend(_render_section_docs(section_document))

    if include_optional:
        for optional_entry in root_document.optional_entries:
            lines.extend(
                [
                    (
                        f'<doc title="{_escape_attr(optional_entry.title)}" '
                        f'desc="{_escape_attr(optional_entry.description)}" '
                        f'url="{_escape_attr(optional_entry.url)}" section="optional" optional="true">'
                    ),
                    _escape_text(optional_entry.description),
                    "</doc>",
                ]
            )

    lines.extend(["</docs>", "</project>"])
    return "\n".join(lines).strip() + "\n"


def _render_section_docs(section_document: SectionDocumentIR) -> list[str]:
    section_lines: list[str] = []
    for processed_page in section_document.pages:
        page_title = processed_page.title or processed_page.h1 or processed_page.url
        page_description = (
            processed_page.meta_description
            or processed_page.og_description
            or "Description unavailable"
        )
        page_body = processed_page.normalized_content or "Content unavailable"
        section_lines.extend(
            [
                (
                    f'<doc title="{_escape_attr(page_title)}" '
                    f'desc="{_escape_attr(page_description)}" '
                    f'url="{_escape_attr(processed_page.url)}" '
                    f'section="{_escape_attr(section_document.section_key)}" optional="false">'
                ),
                _escape_text(page_body),
                "</doc>",
            ]
        )
    return section_lines


def _escape_attr(value: str) -> str:
    return escape(value, quote=True)


def _escape_text(value: str) -> str:
    return escape(value, quote=False)
