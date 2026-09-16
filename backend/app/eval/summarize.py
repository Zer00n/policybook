import csv
import json
from pathlib import Path
from typing import Any

from app.eval.judge import judge_run


def summarize_runs(runs_dir: Path, out_csv_path: Path) -> list[dict[str, Any]]:
    """
    Summarizes all evaluated runs in `runs_dir` into `summary.csv`.
    According to DEV-GUIDE 9.6:
    Contains git commit, prompt version, model ID, seed, etc.
    """
    if not runs_dir.exists():
        runs_dir.mkdir(parents=True, exist_ok=True)

    records = []
    
    # Iterate over subdirectories in runs_dir
    for sub in sorted(runs_dir.iterdir()):
        if not sub.is_dir():
            continue
        meta_file = sub / "meta.json"
        results_file = sub / "results.json"
        if not meta_file.exists() or not results_file.exists():
            continue

        judgments_file = sub / "judgments.json"
        if not judgments_file.exists():
            judge_run(sub)

        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        results = json.loads(results_file.read_text(encoding="utf-8"))
        judgments = json.loads(judgments_file.read_text(encoding="utf-8"))

        total_tokens = sum(r.get("total_tokens", 0) for r in results)
        total_latency = sum(r.get("latency_ms", 0) for r in results)
        count = len(results) or 1
        avg_tokens = round(total_tokens / count, 1)
        avg_latency = round(total_latency / count, 1)

        row = {
            "run_id": meta.get("run_id"),
            "suite": meta.get("suite"),
            "model_alias": meta.get("model_alias"),
            "model_id": meta.get("model_id"),
            "seed": meta.get("seed"),
            "git_commit": meta.get("git_commit"),
            "prompt_version": meta.get("prompt_version", "v1.0"),
            "total_tasks": judgments.get("total_tasks", 0),
            "passed_tasks": judgments.get("passed_tasks", 0),
            "pass_rate": f"{judgments.get('pass_rate_pct', 0.0):.1f}%",
            "verdict_accuracy": f"{judgments.get('verdict_accuracy_pct', 0.0):.1f}%",
            "quote_accuracy": f"{judgments.get('quote_accuracy_pct', 0.0):.1f}%",
            "avg_tokens": avg_tokens,
            "avg_latency_ms": avg_latency,
            "created_at": meta.get("created_at"),
        }
        records.append(row)

    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "suite",
        "model_alias",
        "model_id",
        "seed",
        "git_commit",
        "prompt_version",
        "total_tasks",
        "passed_tasks",
        "pass_rate",
        "verdict_accuracy",
        "quote_accuracy",
        "avg_tokens",
        "avg_latency_ms",
        "created_at",
    ]

    with open(out_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)

    print(f"[+] Summarized {len(records)} runs into {out_csv_path}")
    return records
