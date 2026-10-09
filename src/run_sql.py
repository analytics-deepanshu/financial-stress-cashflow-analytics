"""
Builds the PostgreSQL database and runs every analysis query, saving each result to
sql/results/Qnn_<title>.csv.

Requires the `psql` client on PATH and a reachable PostgreSQL server. Connection settings come
from the standard libpq environment variables (PGHOST, PGPORT, PGUSER, PGPASSWORD); the database
name defaults to `finstress` (override with PGDATABASE). Create it once with:  createdb finstress

Run (from anywhere):  python src/run_sql.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
RESULTS = SQL / "results"


def psql(args: list[str], capture: bool = False) -> str:
    env = {**os.environ, "PGDATABASE": os.environ.get("PGDATABASE", "finstress")}
    cmd = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", *args]
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"psql failed: {' '.join(args)}\n{r.stderr}")
    return r.stdout


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    for f in ("01_schema.sql", "02_load_data.sql", "03_views.sql"):
        out = psql(["-f", f"sql/{f}"])
        if f.startswith("02"):
            print(out.strip())
    text = (SQL / "04_analysis_queries.sql").read_text()
    blocks = re.split(r"(?m)^-- @@ ", text)[1:]
    for b in blocks:
        header = b.splitlines()[0]
        qid, title = [s.strip() for s in header.split("|", 1)]
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40]
        with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as tmp:
            tmp.write("-- " + b)
        out = psql(["--csv", "-f", tmp.name])
        os.unlink(tmp.name)
        (RESULTS / f"{qid}_{slug}.csv").write_text(out)
        print(f"{qid}  {title:<60} {max(len(out.splitlines()) - 1, 0):>4} rows")


if __name__ == "__main__":
    main()
