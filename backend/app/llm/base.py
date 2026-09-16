from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, Sequence
from pydantic import BaseModel


@dataclass
class TextItem:
    text: str


@dataclass
class ImageItem:
    data: bytes  # png or jpeg bytes
    mime_type: str = "image/png"


InputItem = TextItem | ImageItem


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TokenUsage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass
class LLMResult:
    text: str = ""
    parsed: Any | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0
    raw_path: Path | None = None


class LLMProvider(Protocol):
    name: str
    model_id: str

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
        ...

    async def test_connection(self) -> dict[str, Any]:
        ...
