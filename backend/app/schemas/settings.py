from typing import Any
from pydantic import BaseModel, Field


class ModelTestRequest(BaseModel):
    model_key: str | None = Field(default=None, description="模型配置标识，缺省使用默认模型")


class ModelTestResponse(BaseModel):
    ok: bool
    model_id: str
    display_name: str
    latency_ms: int
    reply: str | None = None
    error: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)


class SettingsSummaryResponse(BaseModel):
    app_host: str
    app_port: int
    data_dir: str
    eval_mode: bool
    models: list[dict[str, Any]]
    ark_configured: bool
