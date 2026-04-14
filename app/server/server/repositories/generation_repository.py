from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from server.repositories.generation_types import InflightRunSnapshot
from shared.constants.page_status import FETCH_STATUS_QUEUED, PAGE_STATUS_NEW
from shared.constants.render_mode import RenderModeValue
from shared.constants.run_state import INFLIGHT_RUN_STATES, RUN_STATE_DISCOVERING
from shared.constants.trigger_reason import TRIGGER_REASON_ON_DEMAND
from shared.models.run import Run
from shared.models.run_page import RunPage
from shared.models.site import Site
from shared.pipeline.url_norm import canonical_url


class GenerationRepository:
    def __init__(self, database_session: AsyncSession) -> None:
        self.database_session = database_session

    async def find_or_create_site(
        self,
        root_url: str,
        normalized_host: str,
    ) -> tuple[Site, bool]:
        existing_site = await self.get_site_by_root_url(root_url=root_url)
        if existing_site is not None:
            return existing_site, False

        created_site = Site(root_url=root_url, normalized_host=normalized_host)
        self.database_session.add(created_site)

        try:
            await self.database_session.flush()
            return created_site, True
        except IntegrityError:
            await self.database_session.rollback()

        race_site = await self.get_site_by_root_url(root_url=root_url)
        if race_site is None:
            raise RuntimeError("Site creation failed after integrity conflict")

        return race_site, False

    async def create_run_with_root_page_or_coalesce(
        self,
        site_id: object,
        root_page_url: str,
        render_mode: RenderModeValue,
    ) -> tuple[Run | None, RunPage | None]:
        created_run = Run(
            site_id=site_id,
            trigger_reason=TRIGGER_REASON_ON_DEMAND,
            state=RUN_STATE_DISCOVERING,
        )
        self.database_session.add(created_run)

        normalized_root_page_url = canonical_url(root_page_url)
        created_root_page = RunPage(
            run=created_run,
            url=root_page_url,
            normalized_url=normalized_root_page_url,
            depth=0,
            render_mode=render_mode,
            fetch_status=FETCH_STATUS_QUEUED,
            page_status=PAGE_STATUS_NEW,
        )
        self.database_session.add(created_root_page)

        try:
            await self.database_session.flush()
            return created_run, created_root_page
        except IntegrityError:
            await self.database_session.rollback()
            return None, None

    async def get_site_by_root_url(self, root_url: str) -> Site | None:
        site_statement: Select[tuple[Site]] = select(Site).where(
            Site.root_url == root_url
        )
        site_result = await self.database_session.execute(site_statement)
        return site_result.scalar_one_or_none()

    async def get_inflight_snapshot(
        self, site_id: object
    ) -> InflightRunSnapshot | None:
        run_statement: Select[tuple[Run]] = (
            select(Run)
            .where(Run.site_id == site_id)
            .where(Run.state.in_(INFLIGHT_RUN_STATES))
            .order_by(Run.created_at.desc())
            .limit(1)
        )
        run_result = await self.database_session.execute(run_statement)
        inflight_run = run_result.scalar_one_or_none()
        if inflight_run is None:
            return None

        root_page_statement: Select[tuple[RunPage]] = (
            select(RunPage)
            .where(RunPage.run_id == inflight_run.id)
            .where(RunPage.depth == 0)
            .order_by(RunPage.updated_at.asc())
            .limit(1)
        )
        root_page_result = await self.database_session.execute(root_page_statement)
        root_page = root_page_result.scalar_one_or_none()
        root_page_render_mode = None if root_page is None else root_page.render_mode
        return InflightRunSnapshot(
            run=inflight_run,
            root_render_mode=root_page_render_mode,
        )
