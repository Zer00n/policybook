from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ulid import ULID

from app.db.session import get_db
from app.reports.ppt_builder import build_family_ppt
from app.reports.ppt_verify import verify_ppt_numbers
from app.settings import settings

router = APIRouter(prefix="/reports", tags=["reports"])


class GeneratePPTRequest(BaseModel):
    custom_summary: str | None = Field(None, description="自定义首页简评（可选，不超过90字）")


class PPTReportResponse(BaseModel):
    id: str
    filename: str
    file_size_bytes: int
    slides_count: int
    created_at: str
    verified: bool
    total_checked: int
    mismatches: list[dict[str, Any]]
    snapshot: dict[str, Any]


@router.post("/ppt", response_model=PPTReportResponse)
def generate_ppt_report(
    req: GeneratePPTRequest | None = None,
    db: Session = Depends(get_db),
):
    report_id = str(ULID())
    custom_summary = req.custom_summary if req else None

    # 1. Build PPT
    out_file, snapshot = build_family_ppt(db, report_id=report_id, custom_summary=custom_summary)

    # 2. Re-read and verify (DEV-GUIDE 8.9)
    verify_result = verify_ppt_numbers(out_file, snapshot)

    # Save verification metadata alongside PPT
    meta_file = out_file.with_suffix(".json")
    metadata = {
        "id": report_id,
        "filename": out_file.name,
        "file_size_bytes": out_file.stat().st_size,
        "slides_count": verify_result["slides_count"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verified": verify_result["verified"],
        "total_checked": verify_result["total_checked"],
        "mismatches": verify_result["mismatches"],
        "snapshot": snapshot,
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return PPTReportResponse(**metadata)


@router.get("/ppt", response_model=list[dict[str, Any]])
def list_ppt_reports():
    out_dir = settings.abs_data_dir / "reports"
    if not out_dir.exists():
        return []

    reports = []
    for meta_file in sorted(out_dir.glob("*.json"), reverse=True):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                reports.append(data)
        except Exception:
            continue
    return reports


@router.get("/ppt/{report_id}")
def get_ppt_details(report_id: str):
    out_dir = settings.abs_data_dir / "reports"
    meta_file = out_dir / f"family_report_{report_id}.json"
    if not meta_file.exists():
        raise HTTPException(status_code=404, detail="报告不存在")

    with open(meta_file, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/ppt/{report_id}/download")
def download_ppt(report_id: str):
    out_dir = settings.abs_data_dir / "reports"
    ppt_file = out_dir / f"family_report_{report_id}.pptx"
    if not ppt_file.exists():
        raise HTTPException(status_code=404, detail="PPT 文件不存在")

    return FileResponse(
        path=str(ppt_file),
        filename=f"家庭保单检视报告_{report_id[:8]}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
