import logging
from typing import Any

from handlers.shared.fetcher_adapters.base import FetcherAdapter
from handlers.shared.fetcher_core.repository import FetcherRepository
from handlers.shared.fetcher_storage.raw_html_s3_storage import RawHtmlS3Storage
from shared.logging import log_event
from shared.pipeline.fetch_message import FetchRequestedMessage
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
            metadata_json={
                "child_links_discovered": len(fetched_page.discovered_urls),
                "child_links_accepted": len(bounded_discovered_urls),
            },
        )
        await self.repository.mark_page_completed(run_id=run_id)
        await self.repository.database_session.commit()
        return reserved_children

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
