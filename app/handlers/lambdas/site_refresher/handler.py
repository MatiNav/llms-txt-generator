from typing import Any

from handlers.lambdas.site_refresher.runtime import build_site_refresher_runtime
from handlers.shared.lambda_runtime.base_handler import BaseLambdaHandler


class SiteRefresherLambdaHandler(BaseLambdaHandler):
    def __init__(self) -> None:
        self.runtime = None

    async def process(self, event: dict[str, Any], context: Any) -> dict[str, int]:
        self.runtime = build_site_refresher_runtime()
        cycle_result = (
            await self.runtime.site_refresher_service.refresh_all_sites_once()
        )
        return {
            "scanned_count": cycle_result.scanned_count,
            "published_count": cycle_result.published_count,
            "skipped_inflight_count": cycle_result.skipped_inflight_count,
        }

    async def cleanup(self) -> None:
        if self.runtime is None:
            return
        await self.runtime.site_refresher_service.repository.database_session.close()


site_refresher_lambda_handler = SiteRefresherLambdaHandler()


def handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    return site_refresher_lambda_handler.run(event=event, context=context)
