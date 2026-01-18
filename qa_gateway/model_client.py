import json
from typing import AsyncIterator

import httpx


class ModelClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def stream_chat_completions(self, payload: dict) -> AsyncIterator[bytes]:
        url = f"{self._base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    async def chat_completions(self, payload: dict) -> dict:
        url = f"{self._base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()


def sse_json_lines_from_bytes(buffer: str) -> tuple[list[dict], str]:
    events: list[dict] = []
    while True:
        sep = buffer.find("\n\n")
        if sep == -1:
            break
        block = buffer[:sep]
        buffer = buffer[sep + 2 :]
        for line in block.splitlines():
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                events.append({"_done": True})
                continue
            try:
                events.append(json.loads(data))
            except Exception:
                continue
    return events, buffer


