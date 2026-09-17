import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.eval.faults import FaultInjector, FaultInjectionError
from app.eval.judge import judge_task_e3, judge_run
from app.eval.summarize import summarize_runs
from app.main import app
from conftest import authenticate_async


def test_fault_injector():
    faults = [
        {"tool": "search_web", "on_call": 1, "type": "empty"},
        {"tool": "fetch_document", "on_call": 2, "type": "http_403"},
    ]
    injector = FaultInjector(faults)

    # 1. First call to search_web should return empty
    f1 = injector.record_call("search_web")
    assert f1 is not None
    assert f1["type"] == "empty"

    # 2. First call to fetch_document: normal
    f2_1 = injector.record_call("fetch_document")
    assert f2_1 is None

    # 3. Second call to fetch_document: http_403
    f2_2 = injector.record_call("fetch_document")
    assert f2_2 is not None
    assert f2_2["type"] == "http_403"


def test_judge_task_e3():
    # 1. Covered match
    gold_covered = {
        "verdict": "likely_covered",
        "required_quotes_any": ["意外伤害医疗保险金"],
    }
    result_pass = {
        "task_id": "t1",
        "verdict": "likely_covered",
        "verified_quotes": [{"quote": "意外伤害医疗保险金", "status": "verified", "page": 1}],
    }
    j1 = judge_task_e3(result_pass, gold_covered)
    assert j1["passed"] is True
    assert j1["verdict_correct"] is True
    assert j1["quote_correct"] is True

    # 2. Quote mismatch
    result_fail_quote = {
        "task_id": "t2",
        "verdict": "likely_covered",
        "verified_quotes": [{"quote": "完全不相干的文本", "status": "verified", "page": 1}],
    }
    j2 = judge_task_e3(result_fail_quote, gold_covered)
    assert j2["passed"] is False
    assert j2["verdict_correct"] is True
    assert j2["quote_correct"] is False

    # 3. No basis correct
    gold_no_basis = {"verdict": "no_basis"}
    result_no_basis = {
        "task_id": "t3",
        "verdict": "no_basis",
        "verified_quotes": [],
    }
    j3 = judge_task_e3(result_no_basis, gold_no_basis)
    assert j3["passed"] is True

    # 4. No basis hallucinated
    result_hallucinated = {
        "task_id": "t4",
        "verdict": "likely_covered",
        "verified_quotes": [{"quote": "伪造引用", "status": "verified", "page": 1}],
    }
    j4 = judge_task_e3(result_hallucinated, gold_no_basis)
    assert j4["passed"] is False


def test_judge_run_and_summarize(tmp_path):
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "test_run_001"
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "run_id": "test_run_001",
        "suite": "e3_qa",
        "model_alias": "evolving",
        "model_id": "doubao-seed-evolving",
        "seed": 20260915,
        "git_commit": "abc1234",
        "prompt_version": "v1.0",
        "created_at": "2026-09-16T08:00:00Z",
    }
    results = [
        {
            "task_id": "e3-01",
            "verdict": "likely_covered",
            "verified_quotes": [{"quote": "意外伤害医疗保险金", "status": "verified", "page": 1}],
            "total_tokens": 350,
            "latency_ms": 1200,
            "gold": {
                "verdict": "likely_covered",
                "required_quotes_any": ["意外伤害医疗保险金"],
            },
        },
        {
            "task_id": "e3-17",
            "verdict": "no_basis",
            "verified_quotes": [],
            "total_tokens": 200,
            "latency_ms": 800,
            "gold": {"verdict": "no_basis"},
        },
    ]

    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (run_dir / "results.json").write_text(json.dumps(results), encoding="utf-8")

    # 1. Judge run
    summary = judge_run(run_dir)
    assert summary["total_tasks"] == 2
    assert summary["passed_tasks"] == 2
    assert summary["pass_rate_pct"] == 100.0
    assert (run_dir / "judgments.json").exists()

    # 2. Summarize runs into CSV
    out_csv = tmp_path / "summary.csv"
    rows = summarize_runs(runs_dir, out_csv)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "test_run_001"
    assert rows[0]["pass_rate"] == "100.0%"
    assert out_csv.exists()


@pytest.mark.asyncio
async def test_eval_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await authenticate_async(client)
        resp = await client.get("/api/eval/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "runs" in data
