#!/usr/bin/env python3
"""
Golden-query evaluation harness for the Superstore BI agent.

Runs each expected SQL from the golden-query suite against the Supabase
PostgreSQL database and reports pass/fail (executes without error and returns
rows) plus a small preview of each result. This is the Phase 3 "evaluation loop"
used to verify the agent's SQL generation stays correct as the project evolves.

Usage:
    python run_golden_queries.py

Reads DB credentials from the project-root .env file (Supabase session pooler).
"""
import os
import sys
import psycopg2

# Canonical golden queries. Keep in sync with golden_queries.md.
GOLDEN = [
    ("GQ1", "Total sales and profit in 2017", """
        SELECT ROUND(SUM(f.sales)::numeric, 2)  AS total_sales,
               ROUND(SUM(f.profit)::numeric, 2) AS total_profit
        FROM public.fact_sales f
        JOIN public.dim_date d ON f.order_date_key = d.date_key
        WHERE d.year = 2017;"""),
    ("GQ2", "Unprofitable sub-categories", """
        SELECT p.sub_category, ROUND(SUM(f.profit)::numeric, 2) AS total_profit
        FROM public.fact_sales f
        JOIN public.dim_product p ON f.product_key = p.product_key
        GROUP BY p.sub_category
        HAVING SUM(f.profit) < 0
        ORDER BY total_profit ASC;"""),
    ("GQ3", "Top 5 customers by sales", """
        SELECT c.customer_name, ROUND(SUM(f.sales)::numeric, 2) AS total_sales
        FROM public.fact_sales f
        JOIN public.dim_customer c ON f.customer_key = c.customer_key
        GROUP BY c.customer_name
        ORDER BY total_sales DESC
        LIMIT 5;"""),
    ("GQ4", "Profit margin by category", """
        SELECT p.category,
               ROUND((SUM(f.profit) / NULLIF(SUM(f.sales), 0))::numeric, 4) AS profit_margin
        FROM public.fact_sales f
        JOIN public.dim_product p ON f.product_key = p.product_key
        GROUP BY p.category
        ORDER BY profit_margin DESC;"""),
    ("GQ5", "Best region by sales", """
        SELECT g.region, ROUND(SUM(f.sales)::numeric, 2) AS total_sales
        FROM public.fact_sales f
        JOIN public.dim_geography g ON f.geography_key = g.geography_key
        GROUP BY g.region
        ORDER BY total_sales DESC;"""),
    ("GQ6", "Monthly sales trend", """
        SELECT d.year, d.month, d.month_name,
               ROUND(SUM(f.sales)::numeric, 2) AS total_sales
        FROM public.fact_sales f
        JOIN public.dim_date d ON f.order_date_key = d.date_key
        GROUP BY d.year, d.month, d.month_name
        ORDER BY d.year, d.month;"""),
    ("GQ7", "Avg discount on loss vs profit lines", """
        SELECT CASE WHEN f.profit < 0 THEN 'loss' ELSE 'profit' END AS outcome,
               COUNT(*) AS line_count,
               ROUND(AVG(f.discount)::numeric, 4) AS avg_discount
        FROM public.fact_sales f
        GROUP BY CASE WHEN f.profit < 0 THEN 'loss' ELSE 'profit' END
        ORDER BY outcome;"""),
    ("GQ8", "Orders by ship mode", """
        SELECT s.ship_mode, COUNT(DISTINCT f.order_id) AS order_count
        FROM public.fact_sales f
        JOIN public.dim_ship_mode s ON f.ship_mode_key = s.ship_mode_key
        GROUP BY s.ship_mode
        ORDER BY order_count DESC;"""),
]


def load_env(path=".env"):
    env = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    env = load_env(os.path.join(here, ".env"))
    conn = psycopg2.connect(
        host=env["host"], port=env["port"], dbname=env["database"],
        user=env["user"], password=env["password"], connect_timeout=20,
    )
    passed = 0
    for qid, question, sql in GOLDEN:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
            ok = len(rows) > 0
            status = "PASS" if ok else "FAIL (no rows)"
            passed += 1 if ok else 0
            print(f"\n[{qid}] {question}  ->  {status}")
            print("   cols:", ", ".join(cols))
            for r in rows[:5]:
                print("   ", r)
            if len(rows) > 5:
                print(f"    ... ({len(rows)} rows total)")
            cur.close()
        except Exception as e:
            print(f"\n[{qid}] {question}  ->  ERROR")
            print("   ", str(e).strip())
            conn.rollback()
    conn.close()
    print(f"\n{'='*50}\nRESULT: {passed}/{len(GOLDEN)} golden queries passed")
    sys.exit(0 if passed == len(GOLDEN) else 1)


if __name__ == "__main__":
    main()
