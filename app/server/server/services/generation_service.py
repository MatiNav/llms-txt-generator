import logging

from sqlalchemy.ext.asyncio import AsyncSession

from server.errors.generation import InflightModeConflictError
from server.repositories.generation_repository import GenerationRepository
from shared.constants.render_mode import RenderModeValue
from shared.constants.trigger_reason import TRIGGER_REASON_ON_DEMAND
from shared.models.run import Run
from shared.models.site import Site
from shared.logging import log_event
from shared.pipeline.url_norm import canonical_root_url
from shared.queue.sns_client import SNSClient


logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(
        self,
        database_session: AsyncSession,
        sns_client: SNSClient,
        discoverable_topic_arn: str,
    ) -> None:
        self.database_session = database_session
        self.sns_client = sns_client
        self.discoverable_topic_arn = discoverable_topic_arn
        self.generation_repository = GenerationRepository(
            database_session=database_session
        )

    async def generate(
        self,
        requested_url: str,
        requested_render_mode: RenderModeValue,
        request_id: str | None = None,
    ) -> tuple[Run, bool]:
        canonical_site_root_url, normalized_host = canonical_root_url(requested_url)
        site = await self._find_or_create_site(
            root_url=canonical_site_root_url,
            normalized_host=normalized_host,
            request_id=request_id,
        )

        coalesced_inflight_run = await self._maybe_coalesce_inflight_run(
            site_id=site.id,
            requested_render_mode=requested_render_mode,
            request_id=request_id,
        )
        if coalesced_inflight_run is not None:
            return coalesced_inflight_run, True

        (
            created_run,
            created_root_page,
        ) = await self.generation_repository.create_run_with_root_page_or_coalesce(
            site_id=site.id,
            root_page_url=canonical_site_root_url,
            render_mode=requested_render_mode,
        )

        if created_run is None or created_root_page is None:
            coalesced_race_run = await self._resolve_compatible_inflight_run(
                site_id=site.id,
                requested_render_mode=requested_render_mode,
                request_id=request_id,
                missing_error="Run coalescing failed after integrity conflict",
            )
            if coalesced_race_run is None:
                raise RuntimeError("Run coalescing failed after integrity conflict")
            return coalesced_race_run, True

        await self.database_session.commit()
        await self._publish_discoverable_root_page(
            run_id=str(created_run.id),
            page_id=str(created_root_page.id),
            site_id=str(site.id),
            canonical_site_root_url=canonical_site_root_url,
            requested_render_mode=requested_render_mode,
            request_id=request_id,
        )

        self._log_created_run(
            created_run=created_run,
            site_id=site.id,
            requested_render_mode=requested_render_mode,
            request_id=request_id,
        )
        return created_run, False

    async def _maybe_coalesce_inflight_run(
        self,
        site_id: object,
        requested_render_mode: RenderModeValue,
        request_id: str | None,
    ) -> Run | None:
        return await self._resolve_compatible_inflight_run(
            site_id=site_id,
            requested_render_mode=requested_render_mode,
            request_id=request_id,
        )

    async def _resolve_compatible_inflight_run(
        self,
        site_id: object,
        requested_render_mode: RenderModeValue,
        request_id: str | None,
        missing_error: str | None = None,
    ) -> Run | None:
        inflight_snapshot = await self.generation_repository.get_inflight_snapshot(
            site_id=site_id
        )
        if inflight_snapshot is None:
            if missing_error is not None:
                raise RuntimeError(missing_error)
            return None

        self._ensure_render_mode_compatible(
            requested_render_mode=requested_render_mode,
            inflight_root_render_mode=inflight_snapshot.root_render_mode,
        )
        self._log_coalesced_run(inflight_snapshot.run, site_id, request_id)
        return inflight_snapshot.run

    def _ensure_render_mode_compatible(
        self,
        requested_render_mode: RenderModeValue,
        inflight_root_render_mode: RenderModeValue | None,
    ) -> None:
        if inflight_root_render_mode is None:
            raise RuntimeError("In-flight run is missing root render_mode")

        if inflight_root_render_mode != requested_render_mode:
            raise InflightModeConflictError(
                "An in-flight run already exists for this site with a different render_mode"
            )

    async def _publish_discoverable_root_page(
        self,
        run_id: str,
        page_id: str,
        site_id: str,
        canonical_site_root_url: str,
        requested_render_mode: RenderModeValue,
        request_id: str | None,
    ) -> None:
        await self.sns_client.publish_message(
            topic_arn=self.discoverable_topic_arn,
            payload={
                "run_id": run_id,
                "page_id": page_id,
                "site_id": site_id,
                "url": canonical_site_root_url,
                "depth": 0,
                "render_mode": requested_render_mode,
                "trigger_reason": TRIGGER_REASON_ON_DEMAND,
            },
            request_id=request_id,
        )

    def _log_created_run(
        self,
        created_run: Run,
        site_id: object,
        requested_render_mode: RenderModeValue,
        request_id: str | None,
    ) -> None:
        log_event(
            logger,
            logging.INFO,
            "run.created",
            service="server",
            component="generation_service",
            request_id=request_id,
            run_id=str(created_run.id),
            site_id=str(site_id),
            state=created_run.state,
            render_mode=requested_render_mode,
        )

    async def _find_or_create_site(
        self,
        root_url: str,
        normalized_host: str,
        request_id: str | None = None,
    ) -> Site:
        site, site_created = await self.generation_repository.find_or_create_site(
            root_url=root_url,
            normalized_host=normalized_host,
        )
        if site_created:
            log_event(
                logger,
                logging.INFO,
                "site.created",
                service="server",
                component="generation_service",
                request_id=request_id,
                site_id=str(site.id),
                normalized_host=site.normalized_host,
            )
            return site

        self._log_existing_site(site, request_id)
        return site

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
