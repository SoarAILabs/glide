import os
import asyncio
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from cerebras.cloud.sdk import AsyncCerebras

load_dotenv()

# Default model; override per-call via the `model` argument
DEFAULT_MODEL_ID: str = os.getenv("CEREBRAS_MODEL_ID", "qwen-3-32b")

_async_client: Optional[AsyncCerebras] = None


def _get_api_key(explicit_api_key: Optional[str] = None) -> str:
    api_key = explicit_api_key or os.getenv("CEREBRAS_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "CEREBRAS_API_KEY is not set. Set it in the environment or pass api_key explicitly."
        )
    return api_key


def init_cerebras_async_client(api_key: Optional[str] = None) -> AsyncCerebras:
    """
    Initialize and cache a global AsyncCerebras client.

    Safe to call multiple times; subsequent calls return the cached instance.
    """
    global _async_client
    if _async_client is None:
        _async_client = AsyncCerebras(api_key=_get_api_key(api_key))
    return _async_client


def get_cerebras_async_client() -> AsyncCerebras:
    """Return the cached AsyncCerebras client, initializing it if needed."""
    return init_cerebras_async_client()


async def chat(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    api_key: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Send a structured chat to Cerebras and return the assistant's message content.

    messages: List of {"role": "user"|"system"|"assistant", "content": str}
    model: Model name; defaults to DEFAULT_MODEL_ID
    temperature, max_tokens: Optional generation controls
    api_key: Optional override for API key (avoids relying on env)
    extra_params: Additional keyword arguments passed through to the API
    """
    client = init_cerebras_async_client(api_key)
    response = await client.chat.completions.create(
        messages=messages,
        model=model or DEFAULT_MODEL_ID,
        **({"temperature": temperature} if temperature is not None else {}),
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        **(extra_params or {}),
    )
    return response.choices[0].message.content


async def complete(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    api_key: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Convenience wrapper for single-turn prompts. Builds messages from `system` and `prompt`.
    """
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return await chat(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        extra_params=extra_params,
    )


__all__ = [
    "init_cerebras_async_client",
    "get_cerebras_async_client",
    "chat",
    "complete",
    "DEFAULT_MODEL_ID",
]


if __name__ == "__main__":
    async def _demo() -> None:
        reply = await complete("Why is fast inference important?")
        print(reply)

    asyncio.run(_demo())