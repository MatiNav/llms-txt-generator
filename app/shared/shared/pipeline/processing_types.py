from dataclasses import dataclass


@dataclass(frozen=True)
class PageForProcessing:
    run_page_id: str
    url: str
    normalized_url: str
    depth: int
    html_s3_key: str


@dataclass(frozen=True)
class ProcessedPage:
    run_page_id: str
    url: str
    normalized_url: str
    depth: int
    title: str | None
    meta_description: str | None
    og_description: str | None
    h1: str | None
    internal_links: list[str]
    external_links: list[str]
    mailto_links: list[str]
    breadcrumbs: list[str]
    content_length: int


@dataclass(frozen=True)
class SectionGroup:
    section_key: str
    section_title: str
    pages: list[ProcessedPage]


@dataclass(frozen=True)
class SectionDocumentIR:
    section_key: str
    section_title: str
    summary_placeholder: str
    pages: list[ProcessedPage]


@dataclass(frozen=True)
class OptionalCandidate:
    url: str
    anchor_text: str | None
    source_url: str
    source_kind: str
    raw_context: str | None


@dataclass(frozen=True)
class OptionalDecision:
    category: str
    score: int
    reason: str


@dataclass(frozen=True)
class OptionalEntry:
    title: str
    url: str
    description: str


@dataclass(frozen=True)
class RootDocumentIR:
    root_title: str
    root_summary_placeholder: str
    root_details_placeholder: str
    sections: list[SectionDocumentIR]
    optional_entries: list[OptionalEntry]


@dataclass(frozen=True)
class RenderedFile:
    relative_path: str
    content: str
