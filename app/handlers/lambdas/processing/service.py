import logging

from handlers.lambdas.processing.artifact_storage import ProcessingArtifactStorage
from handlers.lambdas.processing.pipeline import (
    build_document_ir,
    extract_processed_page,
    group_pages_by_section,
    render_documents,
    render_ctx_documents,
    select_eligible_pages,
)
from handlers.lambdas.processing.repository import ProcessingRepository, RunSnapshot
from shared.constants.run_state import (
    RUN_STATE_PROCESSING,
    RUN_STATE_READY_FOR_LLM_GENERATION,
)
from shared.logging import log_decision, log_event
from shared.pipeline.processing_types import (
    PageForProcessing,
    ProcessedPage,
    RenderedFile,
)


logger = logging.getLogger(__name__)


class ProcessingService:
    def __init__(
        self,
        *,
        repository: ProcessingRepository,
        artifact_storage: ProcessingArtifactStorage,
    ) -> None:
        self.repository = repository
        self.artifact_storage = artifact_storage

    async def process_run(self, *, run_id: str, site_id: str) -> bool:
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
            decision_context=decision_context,
        )
        if not queue_is_consistent:
            return self._failed_result()

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
                fetched_page_count=len(fetched_pages),
                extracted_page_count=len(processed_pages),
                decision_context=decision_context,
            )
            return self._failed_result()

        rendered_files = self._build_rendered_outputs(
            eligible_pages=eligible_pages,
            decision_context=decision_context,
        )
        generated_keys = await self._persist_rendered_outputs(
            run_id=run_id,
            rendered_files=rendered_files,
        )
        self._require_generated_key(generated_keys, "llms.txt")
        self._require_generated_key(generated_keys, "llms-ctx.txt")
        self._require_generated_key(generated_keys, "llms-ctx-full.txt")
        await self._finalize_ready_run(
            run_id=run_id,
            site_id=site_id,
            rendered_file_count=len(rendered_files),
        )
        return True

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
    ) -> tuple[bool, bool]:
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
            return True, self._failed_result()

        if run_snapshot.state != RUN_STATE_PROCESSING:
            if run_snapshot.state == RUN_STATE_READY_FOR_LLM_GENERATION:
                log_decision(
                    logger,
                    decision_name="processing.skipped_already_ready_for_llm_generation",
                    reason="run already transitioned to ready_for_llm_generation",
                    run_state=run_snapshot.state,
                    **decision_context,
                )
                return True, self._failed_result()

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

        return False, self._failed_result()

    async def _enforce_queue_consistency(
        self,
        *,
        run_id: str,
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
    ) -> list[RenderedFile]:
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
        rendered_files.extend(render_ctx_documents(root_document))
        return rendered_files

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

    def _require_generated_key(
        self, generated_keys: dict[str, str], relative_path: str
    ) -> str:
        generated_key = generated_keys.get(relative_path)
        if generated_key is None:
            raise RuntimeError(
                f"Rendered output must include required file: {relative_path}"
            )
        return generated_key

    async def _finalize_ready_run(
        self,
        *,
        run_id: str,
        site_id: str,
        rendered_file_count: int,
    ) -> None:
        run_marked_ready = await self.repository.mark_run_ready_for_llm_generation(
            run_id=run_id,
        )
        if not run_marked_ready:
            raise RuntimeError("Run ready_for_llm_generation transition rejected")

        log_event(
            logger,
            logging.INFO,
            "processing.run.ready_for_llm_generation",
            run_id=run_id,
            site_id=site_id,
            rendered_file_count=rendered_file_count,
        )

    @staticmethod
    def _failed_result() -> bool:
        return False

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
                        "normalized_content_length": len(
                            processed_page.normalized_content
                        ),
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
