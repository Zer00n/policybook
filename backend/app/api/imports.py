import json
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ulid import ULID

from app.db.models import Document, Job
from app.db.session import get_db
from app.jobs.events import job_event_generator
from app.schemas.imports import JobResponse, UploadItem, UploadResponse
from app.settings import settings

router = APIRouter(tags=["Imports & Jobs"])


@router.post("/imports", response_model=UploadResponse)
async def upload_policies(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    upload_items: list[UploadItem] = []

    for f in files:
        doc_id = str(ULID())
        job_id = str(ULID())
        filename = f.filename or "policy.pdf"
        suffix = Path(filename).suffix or ".pdf"

        doc_dir = settings.abs_data_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        saved_path = doc_dir / f"original{suffix}"

        content = await f.read()
        with open(saved_path, "wb") as out_file:
            out_file.write(content)

        doc = Document(
            id=doc_id,
            sha256="",
            original_name=filename,
            mime=f.content_type or "application/pdf",
            source="upload",
        )
        db.add(doc)

        job = Job(
            id=job_id,
            kind="import",
            status="queued",
            step="init",
            progress=0.0,
            payload_json=json.dumps({
                "document_id": doc_id,
                "file_path": str(saved_path.resolve()),
                "doc_dir": str(doc_dir.resolve()),
            }),
        )
        db.add(job)
        db.commit()

        upload_items.append(
            UploadItem(
                job_id=job_id,
                document_id=doc_id,
                filename=filename,
            )
        )

    return UploadResponse(jobs=upload_items)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return StreamingResponse(
        job_event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
