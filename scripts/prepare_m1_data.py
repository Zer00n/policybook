import asyncio
import json
from pathlib import Path
from ulid import ULID
from app.db.crypto import encrypt_str
from app.db.init_db import init_db
from app.db.models import Document, Job, Member
from app.db.session import SessionLocal
from app.jobs.queue import worker
from app.settings import settings


async def prepare():
    init_db()
    db = SessionLocal()

    # 1. 确保家庭成员存在
    m1 = db.query(Member).filter(Member.placeholder == "〔成员A〕").first()
    if not m1:
        m1 = Member(
            display_name="爸爸",
            relation="本人",
            birth_year=1980,
            gender="男",
            occupation="高级软件工程师",
            city="北京",
            social_insurance="职工",
            color="#2A8F82",
            placeholder="〔成员A〕",
            real_name_enc=encrypt_str("张伟明"),
        )
        db.add(m1)

    m2 = db.query(Member).filter(Member.placeholder == "〔成员B〕").first()
    if not m2:
        m2 = Member(
            display_name="大宝",
            relation="子女",
            birth_year=2012,
            gender="男",
            occupation="在读学生",
            city="北京",
            social_insurance="居民",
            color="#5E54C9",
            placeholder="〔成员B〕",
            real_name_enc=encrypt_str("张伟"),
        )
        db.add(m2)

    m3 = db.query(Member).filter(Member.placeholder == "〔成员C〕").first()
    if not m3:
        m3 = Member(
            display_name="妈妈",
            relation="配偶",
            birth_year=1982,
            gender="女",
            occupation="产品经理",
            city="北京",
            social_insurance="职工",
            color="#C98217",
            placeholder="〔成员C〕",
            real_name_enc=encrypt_str("李晓华"),
        )
        db.add(m3)

    db.commit()

    # 2. 上传并处理合成保单与扫描件
    fixtures_dir = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"
    pdf_path = fixtures_dir / "synthetic_policy.pdf"
    scanned_path = fixtures_dir / "synthetic_scanned_page.png"

    for file_path, name, mime in [
        (pdf_path, "家庭人身意外伤害保险单.pdf", "application/pdf"),
        (scanned_path, "意外伤害保险批单（扫描件）.png", "image/png"),
    ]:
        if not file_path.exists():
            continue

        doc_id = str(ULID())
        job_id = str(ULID())
        doc_dir = settings.abs_data_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        suffix = file_path.suffix
        saved_path = doc_dir / f"original{suffix}"
        saved_path.write_bytes(file_path.read_bytes())

        doc = Document(
            id=doc_id,
            sha256="",
            original_name=name,
            mime=mime,
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

        print(f"正在处理流水线: {name} (Job: {job_id})...")
        await worker._process_job(job_id)

    db.close()
    print("M1 数据准备完成。")


if __name__ == "__main__":
    asyncio.run(prepare())
