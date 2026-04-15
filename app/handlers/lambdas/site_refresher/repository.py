from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.constants.page_status import FETCH_STATUS_QUEUED, PAGE_STATUS_NEW
from shared.constants.render_mode import RENDER_MODE_HTTP, RenderModeValue
from shared.constants.run_limits import DEFAULT_MAX_PAGES_PER_RUN
from shared.constants.run_state import RUN_STATE_COMPLETED, RUN_STATE_DISCOVERING
from shared.constants.trigger_reason import TRIGGER_REASON_CRON
from shared.models import Run, RunPage, Site
from shared.pipeline.url_norm import canonical_url


@dataclass(frozen=True)
class SiteSeed:
    site_id: str
    site_root_url: str


@dataclass(frozen=True)
class RootRunSeed:
    run_id: str
    page_id: str
    site_id: str
    site_root_url: str
    render_mode: RenderModeValue


class SiteRefresherRepository:
    def __init__(self, database_session: AsyncSession) -> None:
        self.database_session = database_session

    async def list_all_sites(self) -> list[SiteSeed]:
        site_statement: Select[tuple[Site]] = select(Site).order_by(
            Site.created_at.asc()
        )
        site_result = await self.database_session.execute(site_statement)
        all_sites: list[SiteSeed] = []
        for site in site_result.scalars().all():
            all_sites.append(
                SiteSeed(site_id=str(site.id), site_root_url=site.root_url)
            )
        return all_sites

    async def resolve_root_render_mode(self, *, site_id: str) -> RenderModeValue:
        render_mode_statement = (
            select(RunPage.render_mode)
            .join(Run, Run.id == RunPage.run_id)
            .where(Run.site_id == site_id)
            .where(Run.state == RUN_STATE_COMPLETED)
            .where(RunPage.depth == 0)
            .order_by(Run.completed_at.desc().nullslast(), Run.created_at.desc())
            .limit(1)
        )
        render_mode_result = await self.database_session.execute(render_mode_statement)
        root_render_mode = render_mode_result.scalar_one_or_none()
        if root_render_mode is None:
            return RENDER_MODE_HTTP
        return str(root_render_mode)

    async def create_cron_run_with_root_page(
        self,
        *,
        site_id: str,
        site_root_url: str,
        render_mode: RenderModeValue,
    ) -> RootRunSeed:
        created_run = Run(
            site_id=site_id,
            trigger_reason=TRIGGER_REASON_CRON,
            state=RUN_STATE_DISCOVERING,
            max_pages=DEFAULT_MAX_PAGES_PER_RUN,
        )
        self.database_session.add(created_run)

        created_root_page = RunPage(
            run=created_run,
            url=site_root_url,
            normalized_url=canonical_url(site_root_url),
            depth=0,
            render_mode=render_mode,
            fetch_status=FETCH_STATUS_QUEUED,
            page_status=PAGE_STATUS_NEW,
        )
        self.database_session.add(created_root_page)
        await self.database_session.flush()

        return RootRunSeed(
            run_id=str(created_run.id),
            page_id=str(created_root_page.id),
            site_id=site_id,
            site_root_url=site_root_url,
            render_mode=render_mode,
        )
