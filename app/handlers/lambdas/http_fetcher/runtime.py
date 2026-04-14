from dataclasses import dataclass

from handlers.lambdas.http_fetcher.config import load_runtime_config
from handlers.shared.fetcher_adapters.http_adapter import HttpFetcherAdapter
from handlers.shared.fetcher_core.runtime_factory import build_fetcher_core
from handlers.shared.fetcher_core.service import FetcherCoreService
from shared.db.session import get_session_factory


@dataclass(frozen=True)
class HttpFetcherRuntime:
    fetcher_core: FetcherCoreService
    fetcher_adapter: HttpFetcherAdapter


def build_http_fetcher_runtime() -> HttpFetcherRuntime:
    runtime_config = load_runtime_config()
    session_factory = get_session_factory()
    database_session = session_factory()
    fetcher_core = build_fetcher_core(
        database_session=database_session,
        aws_region=runtime_config.aws_region,
        raw_html_bucket_name=runtime_config.raw_html_bucket_name,
        discoverable_topic_arn=runtime_config.discoverable_topic_arn,
        service_name="http_fetcher",
    )

    return HttpFetcherRuntime(
        fetcher_core=fetcher_core,
        fetcher_adapter=HttpFetcherAdapter(),
    )
