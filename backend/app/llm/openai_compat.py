import asyncio
import json
import time
from typing import Any, Sequence
import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import (
    ImageItem,
    InputItem,
    LLMProvider,
    LLMResult,
    TextItem,
    TokenUsage,
    ToolCall,
    ToolSpec,
)
from app.llm.ark import extract_json_from_text
from app.llm.logging import log_llm_call


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        model_id: str,
        base_url: str,
        api_key: str,
        display_name: str = "",
        timeout: float = 120.0,
    ):
        self.name = "openai_compat"
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.display_name = display_name or model_id
        self.timeout = timeout

    async def test_connection(self) -> dict[str, Any]:
        start_time = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 10,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {})
                    choice = data.get("choices", [{}])[0]
                    content = choice.get("message", {}).get("content", "")
                    return {
                        "ok": True,
                        "model_id": self.model_id,
                        "display_name": self.display_name,
                        "reply": content,
                        "latency_ms": latency_ms,
                        "usage": {
                            "input_tokens": usage.get("prompt_tokens", 0),
                            "output_tokens": usage.get("completion_tokens", 0),
                        },
                    }
                else:
                    return {
                        "ok": False,
                        "model_id": self.model_id,
                        "status_code": resp.status_code,
                        "error": resp.text,
                        "latency_ms": latency_ms,
                    }
        except Exception as exc:
            return {
                "ok": False,
                "model_id": self.model_id,
                "error": str(exc),
                "latency_ms": int((time.perf_counter() - start_time) * 1000),
            }

    async def respond(
        self,
        *,
        task_kind: str,
        instructions: str,
        inputs: Sequence[InputItem],
        tools: list[ToolSpec] | None = None,
        output_schema: type[BaseModel] | None = None,
        max_output_tokens: int = 8000,
        stream: bool = False,
    ) -> LLMResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"

        messages: list[dict[str, Any]] = []
        if instructions:
            messages.append({"role": "system", "content": instructions})

        combined_text = "\n\n".join(item.text for item in inputs if isinstance(item, TextItem))
        messages.append({"role": "user", "content": combined_text})

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_output_tokens,
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                usage_dict = data.get("usage", {})
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                reply_text = msg.get("content", "") or ""

                tool_calls: list[ToolCall] = []
                for tc in msg.get("tool_calls", []):
                    fn = tc.get("function", {})
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        args = {}
                    tool_calls.append(
                        ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args)
                    )

                usage = TokenUsage(
                    input_tokens=usage_dict.get("prompt_tokens", 0),
                    output_tokens=usage_dict.get("completion_tokens", 0),
                )

                log_llm_call(
                    task_kind=task_kind,
                    model_id=self.model_id,
                    provider=self.name,
                    latency_ms=latency_ms,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    ok=True,
                    raw_request=payload,
                    raw_response=data,
                )

                parsed_obj = None
                if output_schema:
                    extracted_json = extract_json_from_text(reply_text)
                    if extracted_json is not None:
                        try:
                            parsed_obj = output_schema.model_validate(extracted_json)
                        except ValidationError:
                            pass

                return LLMResult(
                    text=reply_text,
                    parsed=parsed_obj,
                    tool_calls=tool_calls,
                    usage=usage,
                    latency_ms=latency_ms,
                )
            else:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
