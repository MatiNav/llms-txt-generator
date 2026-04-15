import asyncio
from abc import ABC, abstractmethod
from typing import Any

from shared.db.engine import get_engine
from shared.db.session import get_session_factory
from shared.logging import configure_json_logging


class BaseLambdaHandler(ABC):
    async def run_async(self, event: dict[str, Any], context: Any) -> Any:
        try:
            return await self.process(event=event, context=context)
        finally:
            await self.cleanup()
            await self._dispose_cached_db_resources()

    def run(self, event: dict[str, Any], context: Any) -> Any:
        configure_json_logging()
        return asyncio.run(self.run_async(event=event, context=context))

    @abstractmethod
    async def process(self, event: dict[str, Any], context: Any) -> Any: ...

    async def cleanup(self) -> None:
        return None

    async def _dispose_cached_db_resources(self) -> None:
        if get_engine.cache_info().currsize > 0:
            cached_engine = get_engine()
            await cached_engine.dispose()

        get_session_factory.cache_clear()
        get_engine.cache_clear()
