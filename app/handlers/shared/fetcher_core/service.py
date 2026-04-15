import logging
from hashlib import sha256
from typing import Any

from handlers.shared.fetcher_adapters.base import FetcherAdapter
from handlers.shared.fetcher_core.repository import FetcherRepository
from handlers.shared.fetcher_storage.raw_html_s3_storage import RawHtmlS3Storage
from shared.constants.page_status import (
    PAGE_STATUS_CHANGED,
    PAGE_STATUS_NEW,
    PAGE_STATUS_UNCHANGED,
)
from shared.logging import log_event
from shared.pipeline.fetch_message import FetchRequestedMessage
from shared.pipeline.url_norm import canonical_url
from shared.queue.sns_client import SNSClient


logger = logging.getLogger(__name__)


class FetcherCoreService:
    def __init__(
        self,
        *,
        repository: FetcherRepository,
        html_storage: RawHtmlS3Storage,
        discoverable_publisher: SNSClient,
        discoverable_topic_arn: str,
        service_name: str,
    ) -> None:
        self.repository = repository
        self.html_storage = html_storage
        self.discoverable_publisher = discoverable_publisher
        self.discoverable_topic_arn = discoverable_topic_arn
        self.service_name = service_name

    async def process(
        self,
        *,
        fetch_message: FetchRequestedMessage,
        fetcher_adapter: FetcherAdapter,
    ) -> None:
        run_id = fetch_message["run_id"]
        page_id = fetch_message["page_id"]
        was_claimed = await self._claim_or_skip(run_id=run_id, page_id=page_id)
        if not was_claimed:
            return

        try:
            next_depth = fetch_message["depth"] + 1
            reserved_children = await self._fetch_finalize_and_reserve_children(
                fetch_message=fetch_message,
                fetcher_adapter=fetcher_adapter,
                run_id=run_id,
                page_id=page_id,
                next_depth=next_depth,
            )
            await self._publish_page_completed_event(
                run_id=run_id,
                page_id=page_id,
                site_id=fetch_message["site_id"],
            )
            await self._publish_reserved_children(
                fetch_message=fetch_message,
                next_depth=next_depth,
                reserved_children=reserved_children,
            )
        except Exception as processing_error:
            await self._finalize_failure(
                run_id=run_id,
                page_id=page_id,
                site_id=fetch_message["site_id"],
                error_message=str(processing_error),
            )
            raise

    async def _claim_or_skip(self, *, run_id: str, page_id: str) -> bool:
        was_claimed = await self.repository.claim_page(page_id)
        if was_claimed:
            # Persist claim before fetch work starts so failure rollback
            # does not revert the row back to QUEUED.
            await self.repository.database_session.commit()
            return True

        log_event(
            logger,
            logging.INFO,
            "fetch.page.duplicate_skip",
            service=self.service_name,
            run_id=run_id,
            page_id=page_id,
        )
        return False

    async def _fetch_finalize_and_reserve_children(
        self,
        *,
        fetch_message: FetchRequestedMessage,
        fetcher_adapter: FetcherAdapter,
        run_id: str,
        page_id: str,
        next_depth: int,
    ):
        fetched_page = await fetcher_adapter.fetch_page(fetch_message["url"])
        content_hash = self._compute_content_hash(fetched_page.html_content)
        is_root_page = fetch_message["depth"] == 0
        page_status = PAGE_STATUS_NEW
        comparison_method = "none"

        if is_root_page:
            page_status, comparison_method = await self._classify_root_page_status(
                site_id=fetch_message["site_id"],
                page_url=fetch_message["url"],
                etag=fetched_page.etag,
                last_modified=fetched_page.last_modified,
                content_hash=content_hash,
            )

            log_event(
                logger,
                logging.INFO,
                "fetch.root.compare_result",
                service=self.service_name,
                run_id=run_id,
                page_id=page_id,
                site_id=fetch_message["site_id"],
                page_status=page_status,
                comparison_method=comparison_method,
            )
        html_s3_key = await self.html_storage.save_raw_html(
            run_id=run_id,
            page_id=page_id,
            html_content=fetched_page.html_content,
        )

        bounded_discovered_urls = await self._compute_bounded_discovered_urls(
            run_id=run_id,
            next_depth=next_depth,
            discovered_urls=fetched_page.discovered_urls,
        )

        should_skip_children = is_root_page and page_status == PAGE_STATUS_UNCHANGED
        if should_skip_children:
            reserved_children = []
            log_event(
                logger,
                logging.INFO,
                "fetch.root.children_skipped_unchanged",
                service=self.service_name,
                run_id=run_id,
                page_id=page_id,
                site_id=fetch_message["site_id"],
            )
        else:
            reserved_children = await self.repository.reserve_children(
                run_id=run_id,
                depth=next_depth,
                render_mode=fetch_message["render_mode"],
                discovered_urls=bounded_discovered_urls,
            )

        await self.repository.finalize_page_success(
            page_id=page_id,
            html_s3_key=html_s3_key,
            http_status_code=fetched_page.http_status_code,
            etag=fetched_page.etag,
            last_modified=fetched_page.last_modified,
            content_hash=content_hash,
            page_status=page_status,
            metadata_json={
                "child_links_discovered": len(fetched_page.discovered_urls),
                "child_links_accepted": len(bounded_discovered_urls),
                "comparison_method": comparison_method,
            },
        )

        if is_root_page:
            normalized_url = canonical_url(fetch_message["url"])
            await self.repository.upsert_site_page_baseline(
                site_id=fetch_message["site_id"],
                normalized_url=normalized_url,
                run_id=run_id,
                html_s3_key=html_s3_key,
                content_hash=content_hash,
                etag=fetched_page.etag,
                last_modified=fetched_page.last_modified,
            )

        await self.repository.mark_page_completed(run_id=run_id)
        await self.repository.database_session.commit()
        return reserved_children

    async def _classify_root_page_status(
        self,
        *,
        site_id: str,
        page_url: str,
        etag: str | None,
        last_modified: str | None,
        content_hash: str,
    ) -> tuple[str, str]:
        baseline = await self.repository.get_site_page_baseline(
            site_id=site_id,
            normalized_url=canonical_url(page_url),
        )
        if baseline is None:
            return PAGE_STATUS_NEW, "new"

        if baseline.etag and etag:
            status = (
                PAGE_STATUS_UNCHANGED if baseline.etag == etag else PAGE_STATUS_CHANGED
            )
            return status, "etag"

        if baseline.last_modified and last_modified:
            status = (
                PAGE_STATUS_UNCHANGED
                if baseline.last_modified == last_modified
                else PAGE_STATUS_CHANGED
            )
            return status, "last_modified"

        status = (
            PAGE_STATUS_UNCHANGED
            if baseline.content_hash == content_hash
            else PAGE_STATUS_CHANGED
        )
        return status, "content_hash"

    def _compute_content_hash(self, html_content: str) -> str:
        content_bytes = html_content.encode("utf-8")
        return sha256(content_bytes).hexdigest()

    async def _compute_bounded_discovered_urls(
        self,
        *,
        run_id: str,
        next_depth: int,
        discovered_urls: list[str],
    ) -> list[str]:
        run_limits = await self.repository.get_run_limits(run_id)
        if next_depth > run_limits.max_depth:
            return []

        remaining_capacity = max(run_limits.max_pages - run_limits.pages_queued, 0)
        return discovered_urls[:remaining_capacity]

    async def _publish_reserved_children(
        self,
        *,
        fetch_message: FetchRequestedMessage,
        next_depth: int,
        reserved_children,
    ) -> None:
        for reserved_child in reserved_children:
            child_payload: dict[str, Any] = {
                "run_id": fetch_message["run_id"],
                "page_id": reserved_child.page_id,
                "site_id": fetch_message["site_id"],
                "url": reserved_child.url,
                "depth": next_depth,
                "render_mode": fetch_message["render_mode"],
                "trigger_reason": fetch_message["trigger_reason"],
            }
            await self.discoverable_publisher.publish_message(
                topic_arn=self.discoverable_topic_arn,
                payload=child_payload,
            )

    async def _finalize_failure(
        self,
        *,
        run_id: str,
        page_id: str,
        site_id: str,
        error_message: str,
    ) -> None:
        await self.repository.database_session.rollback()
        await self.repository.finalize_page_failure(
            page_id=page_id,
            error_message=error_message,
        )
        await self.repository.mark_page_completed(run_id=run_id)
        await self.repository.database_session.commit()
        await self._publish_page_completed_event(
            run_id=run_id,
            page_id=page_id,
            site_id=site_id,
        )

    async def _publish_page_completed_event(
        self,
        *,
        run_id: str,
        page_id: str,
        site_id: str,
    ) -> None:
        await self.discoverable_publisher.publish_message(
            topic_arn=self.discoverable_topic_arn,
            payload={
                "event_type": "page_completed",
                "run_id": run_id,
                "page_id": page_id,
                "site_id": site_id,
            },
        )
