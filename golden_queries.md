# Golden Queries — Evaluation Suite

A small test suite of natural-language questions paired with the **expected SQL**
against the Superstore star schema. Used to verify the BI agent generates correct,
star-schema-aware SQL. Run `python run_golden_queries.py` to execute each expected
query against Supabase and confirm it runs and returns a sensible result.

The dataset spans order dates **2014–2017**. Whole-dataset totals:
**9,994 line rows, 5,009 orders, ~$2,297,201 sales, ~$286,397 profit.**

---

### GQ1 — Total sales and profit for a given year
**Question:** "What were our total sales and profit in 2017?"
```sql
SELECT ROUND(SUM(f.sales)::numeric, 2)  AS total_sales,
       ROUND(SUM(f.profit)::numeric, 2) AS total_profit
FROM public.fact_sales f
JOIN public.dim_date d ON f.order_date_key = d.date_key
WHERE d.year = 2017;
```
*Tests: role-playing date join (order date), year filter, measure aggregation.*

---

### GQ2 — Unprofitable sub-categories
**Question:** "Which product sub-categories are losing us money?"
```sql
SELECT p.sub_category,
       ROUND(SUM(f.profit)::numeric, 2) AS total_profit
FROM public.fact_sales f
JOIN public.dim_product p ON f.product_key = p.product_key
GROUP BY p.sub_category
HAVING SUM(f.profit) < 0
ORDER BY total_profit ASC;
```
*Tests: dimension join, GROUP BY + HAVING on an aggregate. Expected losers: Tables, Bookcases, Supplies.*

---

### GQ3 — Top 5 customers by sales
**Question:** "Who are our top 5 customers by total sales?"
```sql
SELECT c.customer_name,
       ROUND(SUM(f.sales)::numeric, 2) AS total_sales
FROM public.fact_sales f
JOIN public.dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_name
ORDER BY total_sales DESC
LIMIT 5;
```
*Tests: ranking, LIMIT on a "top N" question.*

---

### GQ4 — Profit margin by category
**Question:** "What is the profit margin for each product category?"
```sql
SELECT p.category,
       ROUND((SUM(f.profit) / NULLIF(SUM(f.sales), 0))::numeric, 4) AS profit_margin
FROM public.fact_sales f
JOIN public.dim_product p ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY profit_margin DESC;
```
*Tests: ratio metric with NULLIF divide-by-zero guard.*

---

### GQ5 — Best region by sales
**Question:** "Which region generates the most sales?"
```sql
SELECT g.region,
       ROUND(SUM(f.sales)::numeric, 2) AS total_sales
FROM public.fact_sales f
JOIN public.dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.region
ORDER BY total_sales DESC;
```
*Tests: geography dimension join, ordering.*

---

### GQ6 — Monthly sales trend
**Question:** "Show me monthly sales over time."
```sql
SELECT d.year, d.month, d.month_name,
       ROUND(SUM(f.sales)::numeric, 2) AS total_sales
FROM public.fact_sales f
JOIN public.dim_date d ON f.order_date_key = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;
```
*Tests: time-series grouping using the date dimension.*

---

### GQ7 — Discount impact on loss-making lines
**Question:** "What's the average discount on order lines that lost money, versus profitable ones?"
```sql
SELECT CASE WHEN f.profit < 0 THEN 'loss' ELSE 'profit' END AS outcome,
       COUNT(*)                          AS line_count,
       ROUND(AVG(f.discount)::numeric, 4) AS avg_discount
FROM public.fact_sales f
GROUP BY CASE WHEN f.profit < 0 THEN 'loss' ELSE 'profit' END
ORDER BY outcome;
```
*Tests: conditional bucketing, measure-only query (no join needed). Reveals discounting drives losses.*

---

### GQ8 — Orders by ship mode
**Question:** "How many distinct orders use each ship mode?"
```sql
SELECT s.ship_mode,
       COUNT(DISTINCT f.order_id) AS order_count
FROM public.fact_sales f
JOIN public.dim_ship_mode s ON f.ship_mode_key = s.ship_mode_key
GROUP BY s.ship_mode
ORDER BY order_count DESC;
```
*Tests: COUNT(DISTINCT order_id) at order grain (not line grain), ship-mode join.*
