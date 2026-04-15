import logging
from dataclasses import dataclass

from handlers.lambdas.processing.artifact_storage import ProcessingArtifactStorage
from handlers.lambdas.processing.pipeline import (
    build_document_ir,
    extract_processed_page,
    group_pages_by_section,
    infer_output_mode,
    render_documents,
    select_eligible_pages,
)
from handlers.lambdas.processing.repository import ProcessingRepository, RunSnapshot
from shared.constants.run_state import RUN_STATE_PROCESSING
from shared.logging import log_decision, log_event
from shared.pipeline.processing_types import (
    PageForProcessing,
    ProcessedPage,
    RenderedFile,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessingResult:
    run_id: str
    site_id: str
    should_publish_llm_generation: bool


@dataclass(frozen=True)
class RenderedOutputBundle:
    rendered_files: list[RenderedFile]
    output_mode: str


class ProcessingService:
    def __init__(
        self,
        *,
        repository: ProcessingRepository,
        artifact_storage: ProcessingArtifactStorage,
    ) -> None:
        self.repository = repository
        self.artifact_storage = artifact_storage

    async def process_run(self, *, run_id: str, site_id: str) -> ProcessingResult:
        decision_context = {
            "run_id": run_id,
            "site_id": site_id,
        }
        run_snapshot = await self._load_run_snapshot_or_raise(run_id)

        is_short_circuited, short_circuit_result = await self._validate_run_context(
            run_snapshot=run_snapshot,
            site_id=site_id,
            decision_context=decision_context,
        )
        if is_short_circuited:
            return short_circuit_result

        queue_is_consistent = await self._enforce_queue_consistency(
            run_id=run_id,
            site_id=site_id,
            decision_context=decision_context,
        )
        if not queue_is_consistent:
            return self._failed_result(run_id=run_id, site_id=site_id)

        fetched_pages = await self.repository.list_fetched_pages_for_processing(run_id)
        processed_pages = await self._extract_pages(
            fetched_pages=fetched_pages,
            decision_context=decision_context,
        )
        eligible_pages = select_eligible_pages(
            processed_pages,
            decision_context=decision_context,
        )
        if not eligible_pages:
            await self._fail_run_for_no_eligible_pages(
                run_id=run_id,
                site_id=site_id,
                fetched_page_count=len(fetched_pages),
                extracted_page_count=len(processed_pages),
                decision_context=decision_context,
            )
            return self._failed_result(run_id=run_id, site_id=site_id)

        rendered_output_bundle = self._build_rendered_outputs(
            eligible_pages=eligible_pages,
            decision_context=decision_context,
        )
        generated_keys = await self._persist_rendered_outputs(
            run_id=run_id,
            rendered_files=rendered_output_bundle.rendered_files,
        )
        root_key = self._require_root_key(generated_keys)
        bundle_key = self._bundle_key_for_mode(
            run_id=run_id,
            output_mode=rendered_output_bundle.output_mode,
        )
        await self._finalize_completed_run(
            run_id=run_id,
            site_id=site_id,
            output_mode=rendered_output_bundle.output_mode,
            root_key=root_key,
            bundle_key=bundle_key,
            rendered_file_count=len(rendered_output_bundle.rendered_files),
        )
        return ProcessingResult(
            run_id=run_id,
            site_id=site_id,
            should_publish_llm_generation=True,
        )

    async def _load_run_snapshot_or_raise(self, run_id: str) -> RunSnapshot:
        run_snapshot = await self.repository.get_run_snapshot(run_id)
        if run_snapshot is None:
            raise RuntimeError(f"Run not found for processing: {run_id}")
        return run_snapshot

    async def _validate_run_context(
        self,
        *,
        run_snapshot: RunSnapshot,
        site_id: str,
        decision_context: dict[str, str],
    ) -> tuple[bool, ProcessingResult]:
        if run_snapshot.site_id != site_id:
            log_decision(
                logger,
                decision_name="processing.rejected_site_id_mismatch",
                reason="message site_id does not match persisted run site_id",
                message_site_id=site_id,
                persisted_site_id=run_snapshot.site_id,
                **decision_context,
            )
            raise RuntimeError("site_id mismatch between message and run")

        if self.repository.is_terminal_state(run_snapshot.state):
            log_decision(
                logger,
                decision_name="processing.skipped_terminal_run",
                reason="run already terminal; no reprocessing needed",
                run_state=run_snapshot.state,
                **decision_context,
            )
            return True, self._failed_result(
                run_id=run_snapshot.run_id,
                site_id=site_id,
            )

        if run_snapshot.state != RUN_STATE_PROCESSING:
            log_decision(
                logger,
                decision_name="processing.rejected_invalid_run_state",
                reason="run must be in processing state for worker execution",
                run_state=run_snapshot.state,
                **decision_context,
            )
            raise RuntimeError(
                f"Run state must be '{RUN_STATE_PROCESSING}', got '{run_snapshot.state}'"
            )

        return False, self._failed_result(
            run_id=run_snapshot.run_id,
            site_id=site_id,
        )

    async def _enforce_queue_consistency(
        self,
        *,
        run_id: str,
        site_id: str,
        decision_context: dict[str, str],
    ) -> bool:
        queued_pages_count = await self.repository.queued_pages_count(run_id)
        if queued_pages_count == 0:
            return True

        log_decision(
            logger,
            decision_name="processing.failed_due_to_queued_pages",
            reason="queued pages present at processing start",
            queued_pages_count=queued_pages_count,
            **decision_context,
        )
        await self.repository.mark_run_failed(
            run_id=run_id,
            error_message="processing_consistency_error: queued pages present",
        )
        return False

    async def _fail_run_for_no_eligible_pages(
        self,
        *,
        run_id: str,
        site_id: str,
        fetched_page_count: int,
        extracted_page_count: int,
        decision_context: dict[str, str],
    ) -> None:
        log_decision(
            logger,
            decision_name="processing.failed_no_eligible_pages",
            reason="no pages passed selection criteria",
            fetched_page_count=fetched_page_count,
            extracted_page_count=extracted_page_count,
            **decision_context,
        )
        await self.repository.mark_run_failed(
            run_id=run_id,
            error_message="no_eligible_pages_after_processing",
        )

    def _build_rendered_outputs(
        self,
        *,
        eligible_pages: list[ProcessedPage],
        decision_context: dict[str, str],
    ) -> RenderedOutputBundle:
        section_groups = group_pages_by_section(
            eligible_pages,
            decision_context=decision_context,
        )
        root_document = build_document_ir(
            section_groups,
            decision_context=decision_context,
        )
        rendered_files = render_documents(
            root_document,
            decision_context=decision_context,
        )
        output_mode = infer_output_mode(
            rendered_files,
            decision_context=decision_context,
        )
        return RenderedOutputBundle(
            rendered_files=rendered_files,
            output_mode=output_mode,
        )

    async def _persist_rendered_outputs(
        self,
        *,
        run_id: str,
        rendered_files: list[RenderedFile],
    ) -> dict[str, str]:
        generated_keys: dict[str, str] = {}
        for rendered_file in rendered_files:
            generated_key = await self.artifact_storage.write_generated_file(
                run_id=run_id,
                relative_path=rendered_file.relative_path,
                content=rendered_file.content,
            )
            generated_keys[rendered_file.relative_path] = generated_key
        return generated_keys

    def _require_root_key(self, generated_keys: dict[str, str]) -> str:
        root_key = generated_keys.get("llms.txt")
        if root_key is None:
            raise RuntimeError("Rendered output must include root llms.txt")
        return root_key

    def _bundle_key_for_mode(self, *, run_id: str, output_mode: str) -> str | None:
        if output_mode != "hierarchical":
            return None
        return self.artifact_storage.generated_bundle_prefix(run_id)

    async def _finalize_completed_run(
        self,
        *,
        run_id: str,
        site_id: str,
        output_mode: str,
        root_key: str,
        bundle_key: str | None,
        rendered_file_count: int,
    ) -> None:
        run_completed = await self.repository.mark_run_completed(
            run_id=run_id,
            output_mode=output_mode,
            root_key=root_key,
            bundle_key=bundle_key,
        )
        if not run_completed:
            raise RuntimeError("Run completion transition rejected")

        log_event(
            logger,
            logging.INFO,
            "processing.run.completed",
            run_id=run_id,
            site_id=site_id,
            output_mode=output_mode,
            root_key=root_key,
            bundle_key=bundle_key,
            rendered_file_count=rendered_file_count,
        )

    @staticmethod
    def _failed_result(*, run_id: str, site_id: str) -> ProcessingResult:
        return ProcessingResult(
            run_id=run_id,
            site_id=site_id,
            should_publish_llm_generation=False,
        )

    async def _extract_pages(
        self,
        *,
        fetched_pages: list[PageForProcessing],
        decision_context: dict[str, str],
    ) -> list[ProcessedPage]:
        processed_pages: list[ProcessedPage] = []
        for fetched_page in fetched_pages:
            try:
                raw_html = await self.artifact_storage.read_raw_html(
                    fetched_page.html_s3_key
                )
                processed_page = extract_processed_page(
                    run_page_id=fetched_page.run_page_id,
                    page_url=fetched_page.url,
                    normalized_url=fetched_page.normalized_url,
                    depth=fetched_page.depth,
                    html_content=raw_html,
                    decision_context=decision_context,
                )
                await self.repository.update_page_metadata(
                    run_page_id=fetched_page.run_page_id,
                    metadata_json={
                        "title": processed_page.title,
                        "meta_description": processed_page.meta_description,
                        "og_description": processed_page.og_description,
                        "h1": processed_page.h1,
                        "breadcrumbs": processed_page.breadcrumbs,
                        "content_length": processed_page.content_length,
                        "internal_links_count": len(processed_page.internal_links),
                        "external_links_count": len(processed_page.external_links),
                        "mailto_links_count": len(processed_page.mailto_links),
                    },
                )
                processed_pages.append(processed_page)
            except Exception as extraction_error:
                log_event(
                    logger,
                    logging.ERROR,
                    "processing.page.extraction_failed",
                    run_id=decision_context["run_id"],
                    site_id=decision_context["site_id"],
                    run_page_id=fetched_page.run_page_id,
                    html_s3_key=fetched_page.html_s3_key,
                    error_type=type(extraction_error).__name__,
                    error_message=str(extraction_error)[:500],
                )
                await self.repository.mark_page_failed_for_processing(
                    run_page_id=fetched_page.run_page_id,
                    error_message=str(extraction_error),
                )
        return processed_pages
