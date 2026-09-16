from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.crypto import decrypt_str
from app.db.models import Document, Page, PiiMapping
from app.db.session import get_db

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    results = []
    for d in docs:
        results.append({
            "id": d.id,
            "original_name": d.original_name,
            "page_count": d.page_count,
            "mime": d.mime,
            "created_at": d.created_at,
        })
    return results


@router.get("/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = db.query(Page).filter(Page.document_id == doc_id).order_by(Page.page_no.asc()).all()
    mappings = db.query(PiiMapping).filter(PiiMapping.document_id == doc_id).all()

    return {
        "id": doc.id,
        "original_name": doc.original_name,
        "page_count": doc.page_count,
        "created_at": doc.created_at,
        "pages": [
            {
                "page_no": p.page_no,
                "is_ocr": p.is_ocr,
                "pii_status": p.pii_status,
                "width": p.width,
                "height": p.height,
            }
            for p in pages
        ],
        "pii_mappings": [
            {
                "placeholder": m.placeholder,
                "kind": m.kind,
            }
            for m in mappings
        ],
    }


@router.get("/{doc_id}/pages/{page_no}/image")
def get_page_image(
    doc_id: str,
    page_no: int,
    masked: int = Query(default=1, description="1 为打码后的图片，0 为原图"),
    db: Session = Depends(get_db),
):
    page = db.query(Page).filter(Page.document_id == doc_id, Page.page_no == page_no).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    if masked and page.masked_image_path:
        img_path = Path(page.masked_image_path)
    else:
        img_path = Path(page.image_path)

    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(img_path, media_type="image/png")


@router.get("/{doc_id}/pages/{page_no}/masked-text")
def get_masked_text(doc_id: str, page_no: int, db: Session = Depends(get_db)):
    page = db.query(Page).filter(Page.document_id == doc_id, Page.page_no == page_no).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"page_no": page_no, "text": page.text_masked or ""}


@router.get("/{doc_id}/pages/{page_no}/pii-compare")
def get_pii_compare(doc_id: str, page_no: int, db: Session = Depends(get_db)):
    page = db.query(Page).filter(Page.document_id == doc_id, Page.page_no == page_no).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    mappings = db.query(PiiMapping).filter(PiiMapping.document_id == doc_id).all()

    return {
        "page_no": page_no,
        "pii_status": page.pii_status,
        "raw_text": decrypt_str(page.text_raw_enc) or "",
        "masked_text": page.text_masked or "",
        "image_url": f"/api/documents/{doc_id}/pages/{page_no}/image?masked=0",
        "masked_image_url": f"/api/documents/{doc_id}/pages/{page_no}/image?masked=1",
        "mappings": [
            {
                "placeholder": m.placeholder,
                "kind": m.kind,
                "value_masked": "******"  # 前端仅展示占位符和掩码形式
            }
            for m in mappings
        ],
    }
