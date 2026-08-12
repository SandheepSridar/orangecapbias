"""
ELT load step: writes ball_by_ball.parquet into the raw schema of ipl.duckdb.
Run this once (or after re-parsing Cricsheet data) before dbt run.

Usage:  python3 src/load_to_duckdb.py
"""

from pathlib import Path
import duckdb

PROJECT = Path(__file__).resolve().parent.parent
PARQUET  = PROJECT / "data/processed/ball_by_ball.parquet"
DB_PATH  = PROJECT / "data/processed/ipl.duckdb"

assert PARQUET.exists(), f"Parquet not found: {PARQUET}\nRun src/parse_cricsheet.py first."

print(f"Loading {PARQUET.name} → {DB_PATH.name} ...")
con = duckdb.connect(str(DB_PATH))
con.execute("CREATE SCHEMA IF NOT EXISTS raw")
con.execute(f"""
    CREATE OR REPLACE TABLE raw.ball_by_ball AS
    SELECT * FROM read_parquet('{PARQUET}')
""")

count = con.execute("SELECT count(*) FROM raw.ball_by_ball").fetchone()[0]
print(f"Loaded {count:,} rows into raw.ball_by_ball")
con.close()
