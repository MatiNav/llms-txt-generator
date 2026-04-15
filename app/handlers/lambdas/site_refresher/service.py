import logging
from dataclasses import dataclass

from handlers.lambdas.site_refresher.repository import SiteRefresherRepository
from shared.logging import log_event
from shared.queue.sns_client import SNSClient
from sqlalchemy.exc import IntegrityError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RefreshCycleResult:
    scanned_count: int
    published_count: int
    skipped_inflight_count: int


class SiteRefresherService:
    def __init__(
        self,
        *,
        repository: SiteRefresherRepository,
        site_refresher_publisher: SNSClient,
        site_refresher_topic_arn: str,
    ) -> None:
        self.repository = repository
        self.site_refresher_publisher = site_refresher_publisher
        self.site_refresher_topic_arn = site_refresher_topic_arn

    async def refresh_all_sites_once(self) -> RefreshCycleResult:
        all_sites = await self.repository.list_all_sites()
        scanned_count = len(all_sites)
        published_count = 0
        skipped_inflight_count = 0

        log_event(
            logger,
            logging.INFO,
            "site_refresher.cycle_started",
            service="site_refresher",
            scanned_count=scanned_count,
        )

        for site in all_sites:
            root_render_mode = await self.repository.resolve_root_render_mode(
                site_id=site.site_id
            )
            try:
                root_seed = await self.repository.create_cron_run_with_root_page(
                    site_id=site.site_id,
                    site_root_url=site.site_root_url,
                    render_mode=root_render_mode,
                )
                await self.repository.database_session.commit()
            except IntegrityError:
                await self.repository.database_session.rollback()
                skipped_inflight_count += 1
                log_event(
                    logger,
                    logging.INFO,
                    "site_refresher.skipped_inflight",
                    service="site_refresher",
                    site_id=site.site_id,
                )
                continue

            log_event(
                logger,
                logging.INFO,
                "site_refresher.run_created",
                service="site_refresher",
                run_id=root_seed.run_id,
                page_id=root_seed.page_id,
                site_id=root_seed.site_id,
                render_mode=root_seed.render_mode,
            )

            await self.site_refresher_publisher.publish_message(
                topic_arn=self.site_refresher_topic_arn,
                payload={
                    "run_id": root_seed.run_id,
                    "page_id": root_seed.page_id,
                    "site_id": root_seed.site_id,
                    "url": root_seed.site_root_url,
                    "depth": 0,
                    "render_mode": root_seed.render_mode,
                    "trigger_reason": "cron",
                },
            )
            published_count += 1

            log_event(
                logger,
                logging.INFO,
                "site_refresher.root_published",
                service="site_refresher",
                run_id=root_seed.run_id,
                page_id=root_seed.page_id,
                site_id=root_seed.site_id,
            )

        log_event(
            logger,
            logging.INFO,
            "site_refresher.cycle_completed",
            service="site_refresher",
            scanned_count=scanned_count,
            published_count=published_count,
            skipped_inflight_count=skipped_inflight_count,
        )
        return RefreshCycleResult(
            scanned_count=scanned_count,
            published_count=published_count,
            skipped_inflight_count=skipped_inflight_count,
        )
