import csv
import json
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException

from app.settings import settings

router = APIRouter(prefix="/eval", tags=["eval"])


@router.get("/summary")
def get_eval_summary():
    """
    Returns summary records from eval/summary.csv, plus all available runs list.
    """
    eval_dir = (settings.project_root / "eval").resolve()
    summary_csv = eval_dir / "summary.csv"
    runs_dir = eval_dir / "runs"

    records = []
    if summary_csv.exists():
        with open(summary_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            records = list(reader)

    runs = []
    if runs_dir.exists():
        for sub in sorted(runs_dir.iterdir(), reverse=True):
            if not sub.is_dir():
                continue
            meta_file = sub / "meta.json"
            judgments_file = sub / "judgments.json"
            if meta_file.exists():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                judgments = json.loads(judgments_file.read_text(encoding="utf-8")) if judgments_file.exists() else {}
                runs.append({
                    "run_id": sub.name,
                    "meta": meta,
                    "summary": {
                        "total_tasks": judgments.get("total_tasks", 0),
                        "passed_tasks": judgments.get("passed_tasks", 0),
                        "pass_rate_pct": judgments.get("pass_rate_pct", 0.0),
                        "verdict_accuracy_pct": judgments.get("verdict_accuracy_pct", 0.0),
                        "quote_accuracy_pct": judgments.get("quote_accuracy_pct", 0.0),
                    }
                })

    return {
        "summary": records,
        "runs": runs,
    }


@router.get("/runs/{run_id}")
def get_eval_run_detail(run_id: str):
    """
    Returns detailed task results and judgments for a specific run.
    """
    eval_dir = (settings.project_root / "eval").resolve()
    run_dir = eval_dir / "runs" / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    meta_file = run_dir / "meta.json"
    results_file = run_dir / "results.json"
    judgments_file = run_dir / "judgments.json"

    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    results = json.loads(results_file.read_text(encoding="utf-8")) if results_file.exists() else []
    judgments = json.loads(judgments_file.read_text(encoding="utf-8")) if judgments_file.exists() else {}

    return {
        "run_id": run_id,
        "meta": meta,
        "results": results,
        "judgments": judgments,
    }
