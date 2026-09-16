import argparse
import asyncio
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from app.eval.judge import judge_run
from app.eval.runner import run_suite
from app.eval.summarize import summarize_runs


def main():
    parser = argparse.ArgumentParser(prog="python -m app.eval", description="PolicyBook Evaluation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. run
    run_parser = subparsers.add_parser("run", help="Run an evaluation task suite with a model")
    run_parser.add_argument("--suite", required=True, type=str, help="Path to suite YAML file")
    run_parser.add_argument("--model", required=True, type=str, help="Model alias (e.g. evolving, pro_0628, baseline)")
    run_parser.add_argument("--seed", default=20260915, type=int, help="Deterministic seed")
    run_parser.add_argument("--out-dir", default=None, type=str, help="Custom output runs directory")

    # 2. judge
    judge_parser = subparsers.add_parser("judge", help="Judge an existing evaluation run")
    judge_parser.add_argument("--run-dir", required=True, type=str, help="Path to run directory")

    # 3. summarize
    sum_parser = subparsers.add_parser("summarize", help="Summarize all runs into summary.csv")
    sum_parser.add_argument("--runs", required=True, type=str, help="Path to runs directory")
    sum_parser.add_argument("--out", required=True, type=str, help="Output CSV path")

    args = parser.parse_args()

    if args.command == "run":
        suite_path = Path(args.suite).resolve()
        out_base = Path(args.out_dir).resolve() if args.out_dir else None
        run_dir = asyncio.run(run_suite(suite_path, args.model, args.seed, out_base))
        print(f"Run finished. Run directory: {run_dir}")

    elif args.command == "judge":
        run_path = Path(args.run_dir).resolve()
        judge_run(run_path)

    elif args.command == "summarize":
        runs_path = Path(args.runs).resolve()
        out_csv = Path(args.out).resolve()
        summarize_runs(runs_path, out_csv)


if __name__ == "__main__":
    main()
