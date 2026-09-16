from datetime import datetime
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



class UploadItem(BaseModel):
    job_id: str
    document_id: str
    filename: str


class UploadResponse(BaseModel):
    jobs: list[UploadItem]
