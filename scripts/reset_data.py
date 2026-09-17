"""
scripts/reset_data.py
清空 PolicyBook 平台的所有业务与测试数据，恢复至纯净初始化状态。
包含：
1. 清空 SQLite 数据库全部业务表及 FTS5 全文索引，并执行 VACUUM 释放空间
2. 清空 data/documents/ 中的所有已上传合同与解析页面、OCR 坐标
3. 清空 data/reports/ 中的所有 PPT 报告
4. 清空 data/llm_raw/ 中的所有模型原始请求与响应
5. 清空 eval/runs/ 中的历史测评跑批数据
"""
import sys
import shutil
from pathlib import Path

# Ensure backend in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import engine, Base
from app.db.init_db import init_db
from app.db.models import (
    Member, Document, Page, PiiMapping, Job, Policy, PolicyParty,
    Coverage, Clause, Evidence, LLMCall, Reminder, AppSetting,
    ChatSession, ChatMessage, SourceRecord, ToolCallRecord
)
from app.settings import settings


def clean_directory(dir_path: Path):
    if not dir_path.exists():
        dir_path.mkdir(parents=True, exist_ok=True)
        return 0

    count = 0
    for item in dir_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            count += 1
        elif item.is_file():
            try:
                item.unlink()
                count += 1
            except Exception as e:
                print(f"  [警告] 无法删除文件 {item}: {e}")
    return count


def reset_database():
    print("-> 正在清空数据库所有数据表...")
    with engine.begin() as conn:
        # Disable foreign keys temporarily during truncate
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF;")
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        
        # Clear FTS5 virtual table if exists
        try:
            conn.exec_driver_sql("DELETE FROM clause_fts;")
        except Exception:
            pass
        
        conn.exec_driver_sql("PRAGMA foreign_keys=ON;")

    # Re-initialize to ensure FTS5 table structure
    init_db()

    # VACUUM outside transaction
    with engine.connect() as conn:
        conn.connection.isolation_level = None
        conn.exec_driver_sql("VACUUM;")
        conn.connection.isolation_level = ""
    print("-> 数据库所有表与 FTS5 索引已清空，并完成磁盘空间回收 (VACUUM)。")


def reset_storage_files():
    data_dir = settings.abs_data_dir
    docs_dir = data_dir / "documents"
    reports_dir = data_dir / "reports"
    llm_raw_dir = data_dir / "llm_raw"
    eval_runs_dir = PROJECT_ROOT / "eval/runs"

    n_docs = clean_directory(docs_dir)
    print(f"-> 已清理 data/documents: 清除 {n_docs} 个文件/目录")

    n_reports = clean_directory(reports_dir)
    print(f"-> 已清理 data/reports: 清除 {n_reports} 个报告文件")

    n_llm = clean_directory(llm_raw_dir)
    print(f"-> 已清理 data/llm_raw: 清除 {n_llm} 个模型调用落盘文件")

    if eval_runs_dir.exists():
        n_eval = clean_directory(eval_runs_dir)
        print(f"-> 已清理 eval/runs: 清除 {n_eval} 个历史测评记录")


def verify_reset():
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        counts = {
            "members": db.query(Member).count(),
            "policies": db.query(Policy).count(),
            "policy_parties": db.query(PolicyParty).count(),
            "documents": db.query(Document).count(),
            "pages": db.query(Page).count(),
            "pii_mappings": db.query(PiiMapping).count(),
            "jobs": db.query(Job).count(),
            "coverages": db.query(Coverage).count(),
            "clauses": db.query(Clause).count(),
            "evidences": db.query(Evidence).count(),
            "reminders": db.query(Reminder).count(),
            "llm_calls": db.query(LLMCall).count(),
            "chat_sessions": db.query(ChatSession).count(),
            "chat_messages": db.query(ChatMessage).count(),
            "source_records": db.query(SourceRecord).count(),
            "tool_calls": db.query(ToolCallRecord).count(),
            "app_settings": db.query(AppSetting).count(),
        }
        print("\n=== 清空后平台数据校验 ===")
        for k, v in counts.items():
            print(f"  {k:15s}: {v}")
        
        all_zero = all(v == 0 for v in counts.values())
        if all_zero:
            print("\n[成功] 平台已完全回归初始化状态，所有数据表均已归零！")
        else:
            print("\n[警告] 部分数据表计数未归零，请检查！")
        return counts
    finally:
        db.close()


def main():
    print("=======================================================")
    print("         PolicyBook 保单簿 · 重置平台测试数据           ")
    print("=======================================================")
    reset_database()
    reset_storage_files()
    verify_reset()


if __name__ == "__main__":
    main()
