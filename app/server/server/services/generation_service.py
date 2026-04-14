import logging

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.run import Run
from shared.models.site import Site
from shared.logging import log_event
from shared.queue.sqs_client import SQSClient
from server.utils.url import normalize_site_url


INFLIGHT_STATES = ("discovering", "processing")
logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(self, database_session: AsyncSession, sqs_client: SQSClient) -> None:
        self.database_session = database_session
        self.sqs_client = sqs_client

    async def generate(
        self, requested_url: str, request_id: str | None = None
    ) -> tuple[Run, bool]:
        canonical_root_url, normalized_host = normalize_site_url(requested_url)

        site = await self._find_or_create_site(
            root_url=canonical_root_url,
            normalized_host=normalized_host,
            request_id=request_id,
        )

        inflight_run = await self._get_inflight_run(site_id=site.id)
        if inflight_run is not None:
            self._log_coalesced_run(inflight_run, site.id, request_id)
            return inflight_run, True

        created_run = await self._create_run_or_coalesce(site_id=site.id)

        if created_run is None:
            inflight_after_race = await self._get_inflight_run(site_id=site.id)
            if inflight_after_race is None:
                raise RuntimeError("Run coalescing failed after integrity conflict")

            self._log_coalesced_run(inflight_after_race, site.id, request_id)
            return inflight_after_race, True

        await self.sqs_client.send_message(
            {
                "run_id": str(created_run.id),
                "site_id": str(site.id),
                "url": canonical_root_url,
                "depth": 0,
            },
            request_id=request_id,
        )

        log_event(
            logger,
            logging.INFO,
            "run.created",
            service="server",
            component="generation_service",
            request_id=request_id,
            run_id=str(created_run.id),
            site_id=str(site.id),
            state=created_run.state,
        )

        return created_run, False

    async def _find_or_create_site(
        self,
        root_url: str,
        normalized_host: str,
        request_id: str | None = None,
    ) -> Site:
        existing_site = await self._get_site_by_root_url(root_url=root_url)
        if existing_site is not None:
            self._log_existing_site(existing_site, request_id)
            return existing_site

        created_site = Site(root_url=root_url, normalized_host=normalized_host)
        self.database_session.add(created_site)

        try:
            await self.database_session.flush()
            log_event(
                logger,
                logging.INFO,
                "site.created",
                service="server",
                component="generation_service",
                request_id=request_id,
                site_id=str(created_site.id),
                normalized_host=created_site.normalized_host,
            )
            return created_site
        except IntegrityError:
            await self.database_session.rollback()

        race_site = await self._get_site_by_root_url(root_url=root_url)
        if race_site is None:
            raise RuntimeError("Site creation failed after integrity conflict")

        self._log_existing_site(race_site, request_id)
        return race_site

    def _log_coalesced_run(
        self,
        run: Run,
        site_id: object,
        request_id: str | None,
    ) -> None:
        log_event(
            logger,
            logging.INFO,
            "run.coalesced",
            service="server",
            component="generation_service",
            request_id=request_id,
            run_id=str(run.id),
            site_id=str(site_id),
            state=run.state,
            coalesced=True,
        )

    def _log_existing_site(self, site: Site, request_id: str | None) -> None:
        log_event(
            logger,
            logging.INFO,
            "site.found_existing",
            service="server",
            component="generation_service",
            request_id=request_id,
            site_id=str(site.id),
            normalized_host=site.normalized_host,
        )

    async def _create_run_or_coalesce(self, site_id: object) -> Run | None:
        created_run = Run(
            site_id=site_id, trigger_reason="on_demand", state="discovering"
        )
        self.database_session.add(created_run)

        try:
            await self.database_session.flush()
            return created_run
        except IntegrityError:
            await self.database_session.rollback()
            return None

    async def _get_site_by_root_url(self, root_url: str) -> Site | None:
        site_statement: Select[tuple[Site]] = select(Site).where(
            Site.root_url == root_url
        )
        site_result = await self.database_session.execute(site_statement)
        return site_result.scalar_one_or_none()

    async def _get_inflight_run(self, site_id: object) -> Run | None:
        run_statement: Select[tuple[Run]] = (
            select(Run)
            .where(Run.site_id == site_id)
            .where(Run.state.in_(INFLIGHT_STATES))
            .order_by(Run.created_at.desc())
            .limit(1)
        )
        run_result = await self.database_session.execute(run_statement)
        return run_result.scalar_one_or_none()
