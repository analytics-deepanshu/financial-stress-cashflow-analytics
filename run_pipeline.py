"""
One command to rebuild the whole project from scratch:

    python run_pipeline.py            # Python steps only
    python run_pipeline.py --sql      # also build the PostgreSQL database and run all queries

Steps
  1. generate_data      synthetic customers + transactions (+ injected data-quality issues)
  2. clean_data         cleaning, validation, data-quality scorecard
  3. features           customer-month table
  4. stress_score       Financial Stress Score per customer (+ monthly history)
  5. cashflow_forecast  next-month cash-flow risk per customer
  6. validate_model     backtest, early-warning test, persona check, weight sensitivity
  7. eda                figures, EDA tables, key metrics
  8. export_powerbi     star-schema CSVs for Power BI
  9. build_excel        management summary workbook
 10. run_sql (optional) PostgreSQL schema, load, views, 20 analysis queries
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["generate_data", "clean_data", "features", "stress_score", "cashflow_forecast",
         "validate_model", "eda", "export_powerbi", "build_excel"]


def run(step: str) -> None:
    t = time.time()
    print(f"\n=== {step} ===", flush=True)
    r = subprocess.run([sys.executable, f"{step}.py"], cwd=ROOT / "src")
    if r.returncode != 0:
        sys.exit(f"Step '{step}' failed.")
    print(f"--- {step} done in {time.time() - t:.1f}s")


if __name__ == "__main__":
    steps = STEPS + (["run_sql"] if "--sql" in sys.argv else [])
    for s in steps:
        run(s)
    print("\nPipeline complete.")
