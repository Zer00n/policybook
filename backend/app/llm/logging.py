import hashlib
import json
from pathlib import Path
from typing import Any
from app.db.models import LLMCall, now_utc
from app.db.session import SessionLocal
from app.settings import settings


def log_llm_call(
    task_kind: str,
    model_id: str,
    provider: str,
    latency_ms: int,
    input_tokens: int = 0,
    cached_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    ok: bool = True,
    error: str | None = None,
    raw_request: Any = None,
    raw_response: Any = None,
    verify_summary: dict[str, Any] | None = None,
) -> str:
    """
    记录 LLM 调用到 llm_call 表，并将脱敏后的原始请求与响应落盘到 data/llm_raw/
    """
    llm_raw_dir = settings.abs_data_dir / "llm_raw"
    llm_raw_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        call = LLMCall(
            task_kind=task_kind,
            model_id=model_id,
            provider=provider,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            latency_ms=latency_ms,
            ok=ok,
            error=error,
            created_at=now_utc(),
        )
        db.add(call)
        db.flush()

        call_id = call.id

        # 生成请求摘要哈希
        req_str = json.dumps(raw_request, ensure_ascii=False) if raw_request is not None else ""
        call.request_digest = hashlib.sha256(req_str.encode("utf-8")).hexdigest()[:16]

        # 原始请求与响应落盘
        raw_file = llm_raw_dir / f"{call_id}.json"
        raw_data = {
            "id": call_id,
            "task_kind": task_kind,
            "model_id": model_id,
            "provider": provider,
            "request": raw_request,
            "response": raw_response,
            "verify_summary": verify_summary,
            "created_at": call.created_at.isoformat(),
        }
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)

        call.response_path = str(raw_file)
        if verify_summary:
            call.verify_summary_json = json.dumps(verify_summary, ensure_ascii=False)

        db.commit()
        return call_id
    except Exception as exc:
        db.rollback()
        # 日志记录失败不应阻断主业务流程
        return ""
    finally:
        db.close()
