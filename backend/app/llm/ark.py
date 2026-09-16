import json
import time
from typing import Any, Sequence
import httpx
from pydantic import BaseModel

from app.llm.base import (
    ImageItem,
    InputItem,
    LLMProvider,
    LLMResult,
    TextItem,
    TokenUsage,
    ToolSpec,
)


class ArkProvider(LLMProvider):
    def __init__(
        self,
        model_id: str,
        base_url: str,
        api_key: str,
        display_name: str = "",
        timeout: float = 60.0,
    ):
        self.name = "ark"
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.display_name = display_name or model_id
        self.timeout = timeout

    async def test_connection(self) -> dict[str, Any]:
        """发起一次最小连通性测试请求，返回耗时、token、响应体概要或错误信息"""
        if not self.api_key:
            return {
                "ok": False,
                "model_id": self.model_id,
                "display_name": self.display_name,
                "error": "ARK_API_KEY 未配置，请在 .env 中设置或通过设置页配置",
                "latency_ms": 0,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

        start_time = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # 兼容火山方舟 Chat Completions / Responses 接口
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "user", "content": "ping"}
            ],
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
                            "total_tokens": usage.get("total_tokens", 0),
                        },
                    }
                else:
                    return {
                        "ok": False,
                        "model_id": self.model_id,
                        "display_name": self.display_name,
                        "status_code": resp.status_code,
                        "error": resp.text,
                        "latency_ms": latency_ms,
                    }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "ok": False,
                "model_id": self.model_id,
                "display_name": self.display_name,
                "error": str(exc),
                "latency_ms": latency_ms,
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
        # 完整抽取与问答在 M2/M3 逐步展开实现
        res = await self.test_connection()
        return LLMResult(
            text=res.get("reply", ""),
            usage=TokenUsage(
                input_tokens=res.get("usage", {}).get("input_tokens", 0),
                output_tokens=res.get("usage", {}).get("output_tokens", 0),
            ),
            latency_ms=res.get("latency_ms", 0),
        )
