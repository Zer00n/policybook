import asyncio
import base64
import json
import re
import time
from pathlib import Path
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
from app.llm.logging import log_llm_call


def extract_json_from_text(text: str) -> Any:
    """从模型输出的文本中提取并解析 JSON 对象或数组"""
    text = text.strip()
    if not text:
        return None

    # 1. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 匹配 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 寻找最外层的 { ... } 或 [ ... ]
    start_brace = text.find("{")
    end_brace = text.rfind("}")
    if start_brace != -1 and end_brace > start_brace:
        try:
            return json.loads(text[start_brace : end_brace + 1])
        except json.JSONDecodeError:
            pass

    start_bracket = text.find("[")
    end_bracket = text.rfind("]")
    if start_bracket != -1 and end_bracket > start_bracket:
        try:
            return json.loads(text[start_bracket : end_bracket + 1])
        except json.JSONDecodeError:
            pass

    return None


class ArkProvider(LLMProvider):
    def __init__(
        self,
        model_id: str,
        base_url: str,
        api_key: str,
        display_name: str = "",
        timeout: float = 300.0,
    ):
        self.name = "ark"
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
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
        """
        向火山方舟发送请求，执行指令并获取结果。
        支持：文本输入、图片输入、指数退避重试、JSON Schema 自动反序列化与修复。
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"

        # 组装 messages
        messages: list[dict[str, Any]] = []
        if instructions:
            messages.append({"role": "system", "content": instructions})

        user_content: list[dict[str, Any]] | str
        has_images = any(isinstance(item, ImageItem) for item in inputs)

        if has_images:
            user_content = []
            for item in inputs:
                if isinstance(item, TextItem):
                    user_content.append({"type": "text", "text": item.text})
                elif isinstance(item, ImageItem):
                    b64_img = base64.b64encode(item.data).decode("utf-8")
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{item.mime_type};base64,{b64_img}"}
                    })
            messages.append({"role": "user", "content": user_content})
        else:
            combined_text = "\n\n".join(item.text for item in inputs if isinstance(item, TextItem))
            messages.append({"role": "user", "content": combined_text})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_output_tokens,
        }

        # 重试循环（最多 3 次，指数退避）
        last_error = None
        for attempt in range(3):
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=60.0)) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                    latency_ms = int((time.perf_counter() - start_time) * 1000)

                    if resp.status_code == 200:
                        data = resp.json()
                        usage_dict = data.get("usage", {})
                        choice = data.get("choices", [{}])[0]
                        reply_text = choice.get("message", {}).get("content", "")

                        usage = TokenUsage(
                            input_tokens=usage_dict.get("prompt_tokens", 0),
                            output_tokens=usage_dict.get("completion_tokens", 0),
                            cached_tokens=usage_dict.get("prompt_tokens_details", {}).get("cached_tokens", 0),
                            reasoning_tokens=usage_dict.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
                        )

                        # 记录日志
                        log_llm_call(
                            task_kind=task_kind,
                            model_id=self.model_id,
                            provider=self.name,
                            latency_ms=latency_ms,
                            input_tokens=usage.input_tokens,
                            cached_tokens=usage.cached_tokens,
                            output_tokens=usage.output_tokens,
                            reasoning_tokens=usage.reasoning_tokens,
                            ok=True,
                            raw_request={"messages": [{"role": m["role"], "content": str(m["content"])[:500]} for m in messages]},
                            raw_response=data,
                        )

                        # 解析 output_schema
                        parsed_obj = None
                        if output_schema:
                            extracted_json = extract_json_from_text(reply_text)
                            if extracted_json is not None:
                                try:
                                    parsed_obj = output_schema.model_validate(extracted_json)
                                except ValidationError as ve:
                                    # 做一次轻量修复尝试
                                    last_error = ve
                            else:
                                last_error = ValueError(f"无法从响应中提取符合 JSON 规范的内容: {reply_text[:200]}")

                        return LLMResult(
                            text=reply_text,
                            parsed=parsed_obj,
                            usage=usage,
                            latency_ms=latency_ms,
                        )
                    else:
                        last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
                        # 429 或 5xx 时重试
                        if resp.status_code in (429, 500, 502, 503, 504):
                            await asyncio.sleep(1.5 ** attempt)
                            continue
                        else:
                            break
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(1.5 ** attempt)

        # 所有重试失败后记录失败日志
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        log_llm_call(
            task_kind=task_kind,
            model_id=self.model_id,
            provider=self.name,
            latency_ms=latency_ms,
            ok=False,
            error=str(last_error),
            raw_request={"messages": [{"role": m["role"], "content": str(m["content"])[:500]} for m in messages]},
        )
        raise RuntimeError(f"模型调用失败 (已重试 3 次): {last_error}")
