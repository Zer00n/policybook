import json
from pathlib import Path
from typing import Any


def normalize_verdict(v: str | None) -> str:
    if not v:
        return "no_basis"
    v = v.lower().strip()
    if v in ["likely_not_covered", "not_covered", "excluded", "uncovered"]:
        return "not_covered"
    if v in ["likely_covered", "covered"]:
        return "likely_covered"
    if v in ["no_basis", "unknown", "none"]:
        return "no_basis"
    return v


def judge_task_e3(result: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    """
    E3 QA Judge according to DEV-GUIDE 9.4:
    - verdict exact match (likely_covered, not_covered, no_basis)
    - required_quotes_any: at least one required quote must match/appear in verified quotes
    - no_basis questions: must NOT answer covered/not_covered
    """
    res_verdict = normalize_verdict(result.get("verdict"))
    gold_verdict = normalize_verdict(gold.get("verdict"))

    verdict_correct = (res_verdict == gold_verdict)
    
    quote_correct = False
    failure_reasons = []

    if not verdict_correct:
        failure_reasons.append(f"Verdict mismatch: expected '{gold_verdict}', got '{res_verdict}'")

    if gold_verdict == "no_basis":
        # For no_basis tasks:
        # If model returned no_basis, quotes should be empty or minimal, quote check passes
        if verdict_correct:
            quote_correct = True
        else:
            failure_reasons.append("Hallucinated answer for no_basis question")
    else:
        req_quotes = gold.get("required_quotes_any", [])
        verified_quotes = [
            vq["quote"] for vq in result.get("verified_quotes", [])
            if vq.get("status") == "verified"
        ]

        if not req_quotes:
            quote_correct = len(verified_quotes) > 0
        else:
            # Check if any required quote appears in the verified quotes
            matched_any = False
            for req in req_quotes:
                for vq in verified_quotes:
                    if req in vq or vq in req:
                        matched_any = True
                        break
                if matched_any:
                    break

            quote_correct = matched_any
            if not quote_correct:
                failure_reasons.append(f"No required quote ({req_quotes}) found in verified citations ({verified_quotes})")

    passed = verdict_correct and quote_correct

    return {
        "task_id": result.get("task_id"),
        "passed": passed,
        "verdict_correct": verdict_correct,
        "quote_correct": quote_correct,
        "model_verdict": res_verdict,
        "gold_verdict": gold_verdict,
        "failure_reasons": failure_reasons,
    }


def judge_run(run_dir: Path) -> dict[str, Any]:
    """
    Evaluates a specific run directory, generating judgments.json.
    DEV-GUIDE 9.2: judge only evaluates existing run traces.
    """
    meta_file = run_dir / "meta.json"
    results_file = run_dir / "results.json"

    if not meta_file.exists() or not results_file.exists():
        raise FileNotFoundError(f"Run directory {run_dir} is missing meta.json or results.json")

    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    results = json.loads(results_file.read_text(encoding="utf-8"))

    suite_name = meta.get("suite", "e3_qa")
    judgments = []

    for r in results:
        gold = r.get("gold", {})
        if suite_name == "e3_qa":
            j = judge_task_e3(r, gold)
        else:
            j = {
                "task_id": r.get("task_id"),
                "passed": False,
                "failure_reasons": ["Suite judge not implemented"],
            }
        judgments.append(j)

    total = len(judgments)
    passed_count = sum(1 for j in judgments if j["passed"])
    verdict_correct_count = sum(1 for j in judgments if j.get("verdict_correct"))
    quote_correct_count = sum(1 for j in judgments if j.get("quote_correct"))

    pass_rate = round(passed_count / total * 100, 2) if total > 0 else 0.0
    verdict_rate = round(verdict_correct_count / total * 100, 2) if total > 0 else 0.0
    quote_rate = round(quote_correct_count / total * 100, 2) if total > 0 else 0.0

    summary = {
        "run_id": meta.get("run_id"),
        "suite": suite_name,
        "model_id": meta.get("model_id"),
        "model_alias": meta.get("model_alias"),
        "total_tasks": total,
        "passed_tasks": passed_count,
        "pass_rate_pct": pass_rate,
        "verdict_accuracy_pct": verdict_rate,
        "quote_accuracy_pct": quote_rate,
        "judgments": judgments,
    }

    out_file = run_dir / "judgments.json"
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[+] Judged run '{meta.get('run_id')}': {passed_count}/{total} passed ({pass_rate}%). Saved to {out_file}")

    return summary
