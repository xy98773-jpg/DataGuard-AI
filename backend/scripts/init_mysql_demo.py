"""Initialize the local MySQL demo database (dg-mysql container).

Creates table `customer` from the demo CSV so Phase 5 can connect,
analyze, plan and preview against a real enterprise-style database.

Usage: python scripts/init_mysql_demo.py
"""

import sys
from pathlib import Path

import pandas as pd
import pymysql

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEMO_CSV = BACKEND_DIR / "datasets" / "demo" / "customer.csv"

CONN = dict(host="127.0.0.1", port=3306, user="root", password="root123", database="dataguard_test")


def main() -> None:
    df = pd.read_csv(DEMO_CSV, dtype={"customer_id": str})
    conn = pymysql.connect(**CONN, charset="utf8mb4")
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS customer")
            cur.execute(
                """
                CREATE TABLE customer (
                    customer_id   VARCHAR(32),
                    name          VARCHAR(64),
                    phone         VARCHAR(32),
                    email         VARCHAR(128),
                    age           INT,
                    register_date VARCHAR(32),
                    amount        DECIMAL(12,2)
                )
                """
            )
            def _s(v):
                return None if pd.isna(v) else str(v)

            rows = [
                (
                    _s(r["customer_id"]), _s(r["name"]), _s(r["phone"]), _s(r["email"]),
                    None if pd.isna(r["age"]) else int(r["age"]),
                    _s(r["register_date"]),
                    None if pd.isna(r["amount"]) else float(r["amount"]),
                )
                for _, r in df.iterrows()
            ]
            cur.executemany(
                "INSERT INTO customer (customer_id,name,phone,email,age,register_date,amount) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                rows,
            )
        conn.commit()
        print(f"MySQL demo initialized: {len(df)} rows in dataguard_test.customer")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
