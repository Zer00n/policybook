from datetime import datetime
from typing import Any
from pydantic import BaseModel


class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    step: str
    progress: float
    error: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobLogItem(BaseModel):
    timestamp: str
    level: str = "info"
    message: str


class ActiveJobItem(BaseModel):
    job_id: str
    document_id: str | None = None
    filename: str
    step: str
    progress: float
    status: str
    error: str | None = None
    logs: list[dict[str, Any]] = []
    created_at: datetime | None = None


class ActiveJobsResponse(BaseModel):
    jobs: list[ActiveJobItem]


class UploadItem(BaseModel):
    job_id: str
    document_id: str
    filename: str


class UploadResponse(BaseModel):
    jobs: list[UploadItem]
