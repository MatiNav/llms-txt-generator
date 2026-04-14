from dataclasses import dataclass

from handlers.ecs_tasks.spa_fetcher.config import load_runtime_config
from handlers.shared.fetcher_adapters.spa_adapter import SpaFetcherAdapter
from handlers.shared.fetcher_core.runtime_factory import build_fetcher_core
from handlers.shared.fetcher_core.service import FetcherCoreService
from shared.db.session import get_session_factory
from shared.queue.sqs_client import SQSClient


@dataclass(frozen=True)
class SpaFetcherRuntime:
    queue_client: SQSClient
    fetcher_core: FetcherCoreService
    fetcher_adapter: SpaFetcherAdapter


def build_spa_fetcher_runtime() -> SpaFetcherRuntime:
    runtime_config = load_runtime_config()
    session_factory = get_session_factory()
    database_session = session_factory()

    queue_client = SQSClient(
        region_name=runtime_config.aws_region,
        queue_url=runtime_config.spa_fetch_queue_url,
    )
    fetcher_core = build_fetcher_core(
        database_session=database_session,
        aws_region=runtime_config.aws_region,
        raw_html_bucket_name=runtime_config.raw_html_bucket_name,
        discoverable_topic_arn=runtime_config.discoverable_topic_arn,
        service_name="spa_fetcher",
    )

    return SpaFetcherRuntime(
        queue_client=queue_client,
        fetcher_core=fetcher_core,
        fetcher_adapter=SpaFetcherAdapter(),
    )
