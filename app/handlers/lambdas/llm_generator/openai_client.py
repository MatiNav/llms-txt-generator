import asyncio

import openai
from openai import AsyncOpenAI


class RetriableLlmError(Exception):
    pass


class FatalLlmError(Exception):
    pass


class OpenAiSummaryClient:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self.model_name = model_name
        self.max_retries = max_retries
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def generate_summary(self, *, prompt: str, max_output_tokens: int) -> str:
        for attempt_index in range(self.max_retries + 1):
            try:
                response = await self.client.responses.create(
                    model=self.model_name,
                    input=prompt,
                    max_output_tokens=max_output_tokens,
                    temperature=0,
                )
                output_text = (response.output_text or "").strip()
                return output_text if output_text else "Summary unavailable"
            except (
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APITimeoutError,
            ) as transient_error:
                if attempt_index >= self.max_retries:
                    raise RetriableLlmError(str(transient_error)) from transient_error
                await asyncio.sleep(2**attempt_index)
            except openai.APIStatusError as status_error:
                if _is_retriable_status(status_error.status_code):
                    if attempt_index >= self.max_retries:
                        raise RetriableLlmError(str(status_error)) from status_error
                    await asyncio.sleep(2**attempt_index)
                    continue
                raise FatalLlmError(str(status_error)) from status_error
            except openai.OpenAIError as openai_error:
                raise FatalLlmError(str(openai_error)) from openai_error


def _is_retriable_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500
