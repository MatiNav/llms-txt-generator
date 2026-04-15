import logging
from dataclasses import dataclass

from handlers.lambdas.llm_generator.artifact_storage import LlmGeneratorArtifactStorage
from handlers.lambdas.llm_generator.openai_client import (
    FatalLlmError,
    OpenAiSummaryClient,
    RetriableLlmError,
)
from handlers.lambdas.llm_generator.repository import (
    LlmGenerationRunContext,
    LlmGeneratorRepository,
    PageSummaryContext,
)
from shared.constants.run_state import RUN_STATE_READY_FOR_LLM_GENERATION
from shared.logging import log_decision, log_event
from shared.pipeline.summary_placeholders import (
    apply_replacements,
    extract_placeholders,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaceholderDescriptor:
    token: str
    token_kind: str
    section_key: str | None
    page_url: str | None


class LlmGeneratorService:
    def __init__(
        self,
        *,
        repository: LlmGeneratorRepository,
        artifact_storage: LlmGeneratorArtifactStorage,
        openai_client: OpenAiSummaryClient,
    ) -> None:
        self.repository = repository
        self.artifact_storage = artifact_storage
        self.openai_client = openai_client

    async def process_run(self, *, run_id: str, site_id: str) -> None:
        run_context = await self._load_run_context(run_id=run_id, site_id=site_id)
        if run_context is None:
            return

        try:
            generated_keys = await self.artifact_storage.list_generated_keys(run_id)
            if not generated_keys:
                raise FatalLlmError("No generated artifacts found for llm generation")

            if (
                run_context.llms_txt_s3_key is None
                and run_context.bundle_s3_key is None
            ):
                raise FatalLlmError("Run has no output pointers for llm generation")

            page_context_by_url = await self.repository.get_page_context_by_url(run_id)
            replacement_count = await self._enrich_generated_files(
                run_id=run_id,
                generated_keys=generated_keys,
                page_context_by_url=page_context_by_url,
            )

            run_completed = await self.repository.mark_run_completed(run_id)
            if not run_completed:
                raise FatalLlmError(
                    "Run completion transition rejected for llm generation"
                )

            log_event(
                logger,
                logging.INFO,
                "llm_generator.run.completed",
                run_id=run_id,
                site_id=site_id,
                generated_file_count=len(generated_keys),
                replacement_count=replacement_count,
            )
        except RetriableLlmError:
            raise
        except FatalLlmError as processing_error:
            await self._fail_run_if_possible(
                run_id=run_id, site_id=site_id, error=processing_error
            )
            raise
        except Exception:
            raise

    async def _load_run_context(
        self,
        *,
        run_id: str,
        site_id: str,
    ) -> LlmGenerationRunContext | None:
        run_context = await self.repository.get_run_context(run_id)
        if run_context is None:
            raise FatalLlmError(f"Run not found for llm generation: {run_id}")

        if run_context.site_id != site_id:
            raise FatalLlmError(
                "site_id mismatch between llm generation message and run"
            )

        if self.repository.is_terminal_state(run_context.state):
            log_decision(
                logger,
                decision_name="llm_generator.skip_terminal_run",
                reason="run already terminal; no llm generation needed",
                run_id=run_id,
                site_id=site_id,
                run_state=run_context.state,
            )
            return None

        if run_context.state != RUN_STATE_READY_FOR_LLM_GENERATION:
            log_decision(
                logger,
                decision_name="llm_generator.skip_not_ready_state",
                reason="run is not ready_for_llm_generation",
                run_id=run_id,
                site_id=site_id,
                run_state=run_context.state,
            )
            return None

        return run_context

    async def _enrich_generated_files(
        self,
        *,
        run_id: str,
        generated_keys: list[str],
        page_context_by_url: dict[str, PageSummaryContext],
    ) -> int:
        replacement_count = 0
        for generated_key in generated_keys:
            file_content = await self.artifact_storage.read_text(generated_key)
            placeholder_tokens = extract_placeholders(file_content)
            if not placeholder_tokens:
                continue

            replacements = await self._build_replacements(
                placeholder_tokens=placeholder_tokens,
                page_context_by_url=page_context_by_url,
            )
            if not replacements:
                continue

            enriched_content = apply_replacements(file_content, replacements)
            await self.artifact_storage.write_text(
                generated_key,
                enriched_content,
                run_id=run_id,
            )
            replacement_count += len(replacements)

        return replacement_count

    async def _build_replacements(
        self,
        *,
        placeholder_tokens: list[str],
        page_context_by_url: dict[str, PageSummaryContext],
    ) -> dict[str, str]:
        replacements: dict[str, str] = {}
        unique_tokens = sorted(set(placeholder_tokens))

        for placeholder_token in unique_tokens:
            descriptor = _parse_placeholder_token(placeholder_token)
            if descriptor is None:
                log_decision(
                    logger,
                    decision_name="llm_generator.skip_unknown_placeholder",
                    reason="placeholder format is not supported by llm generator",
                    placeholder_token=placeholder_token,
                )
                continue

            replacements[placeholder_token] = await self._generate_replacement_text(
                descriptor=descriptor,
                page_context_by_url=page_context_by_url,
            )

        return replacements

    async def _generate_replacement_text(
        self,
        *,
        descriptor: PlaceholderDescriptor,
        page_context_by_url: dict[str, PageSummaryContext],
    ) -> str:
        if descriptor.token_kind == "root_summary":
            prompt = _build_root_summary_prompt()
            return await self.openai_client.generate_summary(
                prompt=prompt,
                max_output_tokens=80,
            )

        if descriptor.token_kind == "root_details":
            prompt = _build_root_details_prompt()
            return await self.openai_client.generate_summary(
                prompt=prompt,
                max_output_tokens=200,
            )

        if descriptor.token_kind == "section_summary":
            prompt = _build_section_prompt(
                section_key=descriptor.section_key or "unknown",
                short_summary=False,
            )
            return await self.openai_client.generate_summary(
                prompt=prompt,
                max_output_tokens=140,
            )

        if descriptor.token_kind == "section_short_summary":
            prompt = _build_section_prompt(
                section_key=descriptor.section_key or "unknown",
                short_summary=True,
            )
            return await self.openai_client.generate_summary(
                prompt=prompt,
                max_output_tokens=60,
            )

        if descriptor.token_kind == "page_summary" and descriptor.page_url is not None:
            page_context = page_context_by_url.get(descriptor.page_url)
            if page_context is None:
                return "Summary unavailable"

            prompt = _build_page_prompt(page_context)
            return await self.openai_client.generate_summary(
                prompt=prompt,
                max_output_tokens=120,
            )

        return "Summary unavailable"

    async def _fail_run_if_possible(
        self,
        *,
        run_id: str,
        site_id: str,
        error: Exception,
    ) -> None:
        run_failed = await self.repository.mark_run_failed(
            run_id=run_id,
            error_message=str(error),
        )
        log_event(
            logger,
            logging.ERROR,
            "llm_generator.run.failed",
            run_id=run_id,
            site_id=site_id,
            error_type=type(error).__name__,
            error_message=str(error)[:500],
            run_failed=run_failed,
        )


def _parse_placeholder_token(placeholder_token: str) -> PlaceholderDescriptor | None:
    if not placeholder_token.startswith(
        "{{LLM_SUMMARY:"
    ) or not placeholder_token.endswith("}}"):
        return None

    token_content = placeholder_token[len("{{LLM_SUMMARY:") : -2]
    token_parts = token_content.split(":")
    if token_parts == ["root"]:
        return PlaceholderDescriptor(
            token=placeholder_token,
            token_kind="root_summary",
            section_key=None,
            page_url=None,
        )
    if token_parts == ["root", "details"]:
        return PlaceholderDescriptor(
            token=placeholder_token,
            token_kind="root_details",
            section_key=None,
            page_url=None,
        )
    if len(token_parts) == 2 and token_parts[0] == "section":
        return PlaceholderDescriptor(
            token=placeholder_token,
            token_kind="section_summary",
            section_key=token_parts[1],
            page_url=None,
        )
    if (
        len(token_parts) == 3
        and token_parts[0] == "section"
        and token_parts[2] == "short"
    ):
        return PlaceholderDescriptor(
            token=placeholder_token,
            token_kind="section_short_summary",
            section_key=token_parts[1],
            page_url=None,
        )
    if token_content.startswith("page:"):
        page_url = token_content[len("page:") :]
        return PlaceholderDescriptor(
            token=placeholder_token,
            token_kind="page_summary",
            section_key=None,
            page_url=page_url,
        )
    return None


def _build_root_summary_prompt() -> str:
    return (
        "Write a concise one-line summary for the root llms.txt file. "
        "Return plain text only."
    )


def _build_root_details_prompt() -> str:
    return (
        "Write a short paragraph describing the website scope for llms.txt readers. "
        "Return plain text only and avoid markdown headers."
    )


def _build_section_prompt(*, section_key: str, short_summary: bool) -> str:
    if short_summary:
        return (
            f"Write a very short phrase describing the '{section_key}' section. "
            "Return plain text only."
        )
    return (
        f"Write a concise paragraph describing the '{section_key}' section for llms.txt. "
        "Return plain text only."
    )


def _build_page_prompt(page_context: PageSummaryContext) -> str:
    title_text = page_context.title or ""
    h1_text = page_context.h1 or ""
    meta_description_text = (
        page_context.meta_description or page_context.og_description or ""
    )
    content_length_text = (
        str(page_context.content_length)
        if page_context.content_length is not None
        else "unknown"
    )

    return (
        "Summarize the following webpage for an llms.txt index in one concise sentence.\n"
        f"URL: {page_context.url}\n"
        f"Title: {title_text}\n"
        f"Heading: {h1_text}\n"
        f"Description: {meta_description_text}\n"
        f"Content length: {content_length_text}"
    )
