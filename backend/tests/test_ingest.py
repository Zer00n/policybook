import asyncio
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.db.models import Job
from app.db.session import SessionLocal
from app.jobs.queue import worker
from app.main import app
from conftest import authenticate

client = TestClient(app)
authenticate(client)
fixtures_dir = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_synthetic_policy_upload_and_pipeline():
    pdf_path = fixtures_dir / "synthetic_policy.pdf"
    assert pdf_path.exists(), "Fixtures must be generated"

    # 上传保单
    with open(pdf_path, "rb") as f:
        res = client.post(
            "/api/imports",
            files={"files": ("synthetic_policy.pdf", f, "application/pdf")},
        )
    assert res.status_code == 200
    data = res.json()
    assert len(data["jobs"]) == 1

    job_id = data["jobs"][0]["job_id"]
    doc_id = data["jobs"][0]["document_id"]

    # 执行 pipeline 处理该任务（mock 步骤 5-10 的大模型在线调用以保持单元测试隔离与高执行速度）
    with patch("app.ingest.extract.run_document_extraction", new=AsyncMock(return_value={"mock": True})):
        await worker._process_job(job_id)

    # 验证任务完成
    job_res = client.get(f"/api/jobs/{job_id}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "succeeded"
    assert job_data["progress"] == 1.0

    # 验证文档详情
    doc_res = client.get(f"/api/documents/{doc_id}")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["page_count"] == 2
    assert len(doc_data["pages"]) == 2
    assert doc_data["pages"][0]["pii_status"] == "success"

    # 验证对比接口数据
    compare_res = client.get(f"/api/documents/{doc_id}/pages/1/pii-compare")
    assert compare_res.status_code == 200
    comp_data = compare_res.json()
    assert comp_data["pii_status"] == "success"
    assert "110101199003072375" in comp_data["raw_text"]
    assert "110101199003072375" not in comp_data["masked_text"]
    assert "〔证件" in comp_data["masked_text"]
    assert "〔电话" in comp_data["masked_text"]
    assert "〔卡号" in comp_data["masked_text"]



@pytest.mark.asyncio
async def test_scanned_page_ocr_and_pii():
    scanned_path = fixtures_dir / "synthetic_scanned_page.png"
    assert scanned_path.exists()

    with open(scanned_path, "rb") as f:
        res = client.post(
            "/api/imports",
            files={"files": ("scanned_page.png", f, "image/png")},
        )
    assert res.status_code == 200
    data = res.json()
    job_id = data["jobs"][0]["job_id"]
    doc_id = data["jobs"][0]["document_id"]

    with patch("app.ingest.extract.run_document_extraction", new=AsyncMock(return_value={"mock": True})):
        await worker._process_job(job_id)

    job_res = client.get(f"/api/jobs/{job_id}")
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "succeeded"

    doc_res = client.get(f"/api/documents/{doc_id}")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["page_count"] == 1
    # 扫描页必须标记 is_ocr = True
    assert doc_data["pages"][0]["is_ocr"] is True
    assert doc_data["pages"][0]["pii_status"] == "success"

    # 验证 OCR 提取并成功脱敏
    compare_res = client.get(f"/api/documents/{doc_id}/pages/1/pii-compare")
    assert compare_res.status_code == 200
    comp = compare_res.json()
    assert "110101199003072375" not in comp["masked_text"]
    assert "〔证件" in comp["masked_text"]


def test_job_restart_recovery():
    db = SessionLocal()
    try:
        # 伪造一个正在运行中突然崩溃中断的 job
        j = Job(
            kind="import",
            status="running",
            step="render",
            progress=0.3,
            attempts=0,
        )
        db.add(j)
        db.commit()
        db.refresh(j)
        crashed_id = j.id

        # 触发服务重启恢复函数
        worker.reset_stale_jobs()

        db.expire_all()
        recovered_job = db.query(Job).filter(Job.id == crashed_id).first()
        assert recovered_job is not None
        assert recovered_job.status == "queued"
        assert recovered_job.attempts == 1


        db.delete(recovered_job)
        db.commit()
    finally:
        db.close()
