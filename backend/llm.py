import asyncio
import os
import time

from anthropic import AsyncAnthropic

_SONNET_TRIGGERS = (
    "draft",
    "write",
    "generate",
    "create",
    "why",
    "explain",
    "should i",
    "compare",
    "recommend",
    "improve",
    "rewrite",
)

_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
_SONNET_MODEL = os.environ["ZEE_MODEL_SONNET"]
_HAIKU_MODEL = os.environ["ZEE_MODEL_HAIKU"]


def pick_model(message: str) -> str:
    lowered = message.lower()
    if any(trigger in lowered for trigger in _SONNET_TRIGGERS):
        return _SONNET_MODEL
    if len(message.split()) > 30:
        return _SONNET_MODEL
    return _HAIKU_MODEL


async def chat(messages, system, model, tools=None, max_tokens=1024):
    delays = (0.5, 1.0, 2.0)
    last_error: Exception | None = None

    for attempt, delay in enumerate(delays):
        started = time.perf_counter()
        try:
            kwargs = {
                "model": model,
                "system": system,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            if tools is not None:
                kwargs["tools"] = tools

            response = await _client.messages.create(**kwargs)
            latency_ms = int((time.perf_counter() - started) * 1000)

            return {
                "content": [block.model_dump() for block in response.content],
                "stop_reason": response.stop_reason,
                "usage": {
                    "model": response.model,
                    "tokens_in": response.usage.input_tokens,
                    "tokens_out": response.usage.output_tokens,
                    "latency_ms": latency_ms,
                },
            }
        except Exception as exc:
            last_error = exc
            if attempt == len(delays) - 1:
                raise
            await asyncio.sleep(delay)

    raise RuntimeError("chat failed without raising") from last_error
