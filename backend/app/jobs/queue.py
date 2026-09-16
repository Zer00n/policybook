import asyncio
import hashlib
import json
from pathlib import Path
from sqlalchemy.orm import Session

from app.db.crypto import decrypt_str, encrypt_str
from app.db.models import Document, Job, Member, Page, PiiMapping
from app.db.session import SessionLocal
from app.ingest.ocr import ocr_page
from app.ingest.pii import PiiDeidentifier, apply_visual_masking
from app.ingest.render import render_file_to_pages
from app.jobs.events import broadcaster


class JobWorker:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    def reset_stale_jobs(self):
        """服务重启时把 running 状态的任务重置为 queued，支持断点恢复"""
        db = SessionLocal()
        try:
            stale_jobs = db.query(Job).filter(Job.status == "running").all()
            for job in stale_jobs:
                job.status = "queued"
                job.attempts += 1
            db.commit()
        finally:
            db.close()

    async def _loop(self):
        self.reset_stale_jobs()
        while self._running:
            try:
                job_id = self._pick_next_job()
                if job_id:
                    await self._process_job(job_id)
                else:
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(1.0)

    def _pick_next_job(self) -> str | None:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.status == "queued").order_by(Job.created_at.asc()).first()
            if job:
                job.status = "running"
                db.commit()
                return job.id
            return None
        finally:
            db.close()

    async def _process_job(self, job_id: str):
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return

            payload = json.loads(job.payload_json or "{}")
            kind = job.kind

            if kind == "import":
                await self._run_import_pipeline(db, job, payload)
            else:
                job.status = "succeeded"
                job.progress = 1.0
                db.commit()
        except Exception as exc:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error = str(exc)
                db.commit()
            await broadcaster.broadcast(job_id, "error", {"code": "JOB_ERROR", "message": str(exc)})
        finally:
            db.close()

    async def _run_import_pipeline(self, db: Session, job: Job, payload: dict):
        document_id = payload.get("document_id")
        file_path_str = payload.get("file_path")
        doc_dir_str = payload.get("doc_dir")

        if not document_id or not file_path_str or not doc_dir_str:
            raise ValueError("Invalid import payload")

        file_path = Path(file_path_str)
        doc_dir = Path(doc_dir_str)

        # 步骤 1: 计算文件哈希
        await broadcaster.broadcast(job.id, "step", {"job_id": job.id, "step": "hash_check", "progress": 0.1})
        job.step = "hash_check"
        job.progress = 0.1
        db.commit()

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        sha256_val = hasher.hexdigest()

        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.sha256 = sha256_val
            db.commit()

        # 步骤 2: 页面渲染与字符坐标提取 (PyMuPDF)
        await broadcaster.broadcast(job.id, "step", {"job_id": job.id, "step": "render", "progress": 0.3})
        job.step = "render"
        job.progress = 0.3
        db.commit()

        rendered_pages = await asyncio.to_thread(render_file_to_pages, file_path, doc_dir)

        # 写入 Page 记录
        pages_db = []
        for rp in rendered_pages:
            p = Page(
                document_id=document_id,
                page_no=rp.page_no,
                image_path=str(rp.image_path.resolve()),
                char_map_path=str(rp.char_map_path.resolve()),
                text_raw_enc=encrypt_str(rp.raw_text),
                is_ocr=rp.is_ocr,
                width=rp.width_px,
                height=rp.height_px,
            )
            db.add(p)
            pages_db.append(p)
        if doc:
            doc.page_count = len(rendered_pages)
        db.commit()

        # 步骤 3: 扫描判定与 OCR 识别
        await broadcaster.broadcast(job.id, "step", {"job_id": job.id, "step": "ocr", "progress": 0.6})
        job.step = "ocr"
        job.progress = 0.6
        db.commit()

        for p, rp in zip(pages_db, rendered_pages):
            if p.is_ocr:
                ocr_text = await asyncio.to_thread(ocr_page, rp.image_path, rp.char_map_path)
                p.text_raw_enc = encrypt_str(ocr_text)
                rp.raw_text = ocr_text
        db.commit()

        # 步骤 4: 本地脱敏与打码
        await broadcaster.broadcast(job.id, "step", {"job_id": job.id, "step": "pii", "progress": 0.85})
        job.step = "pii"
        job.progress = 0.85
        db.commit()

        # 读取已登记家庭成员真实姓名进行匹配
        members = db.query(Member).all()
        registered_members = []
        for m in members:
            real_name = decrypt_str(m.real_name_enc)
            if real_name:
                registered_members.append({"real_name": real_name, "placeholder": m.placeholder})

        deidentifier = PiiDeidentifier(registered_members)

        for p, rp in zip(pages_db, rendered_pages):
            raw_text = decrypt_str(p.text_raw_enc) or ""
            res = deidentifier.deidentify_text(raw_text)

            masked_img_path = doc_dir / f"p{rp.page_no:03d}_masked.png"
            apply_visual_masking(rp.image_path, rp.char_map_path, res.spans, masked_img_path)

            p.masked_image_path = str(masked_img_path.resolve())
            p.text_masked = res.masked_text
            p.pii_status = res.pii_status

            # 保存 mappings 到 pii_mapping
            for item in res.mappings:
                mapping = PiiMapping(
                    document_id=document_id,
                    placeholder=item["placeholder"],
                    kind=item["kind"],
                    value_enc=encrypt_str(item["value"]) or "",
                )
                db.add(mapping)
        db.commit()

        # M1 阶段完成至脱敏为止
        job.step = "pii"
        job.progress = 1.0
        job.status = "succeeded"
        db.commit()

        await broadcaster.broadcast(job.id, "step", {"job_id": job.id, "step": "pii", "progress": 1.0})
        await broadcaster.broadcast(job.id, "done", {"job_id": job.id, "document_id": document_id})


worker = JobWorker()
