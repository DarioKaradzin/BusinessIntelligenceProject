"""
build_star_schema.py

End-to-end ETL script to build a Kimball star schema in Supabase PostgreSQL
from 'data/Sample - Superstore.csv' and load all dimensions and fact tables.
"""

import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


def load_env(env_path=".env"):
    """Read connection credentials from .env file."""
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Environment file not found at: {env_path}")
    
    creds = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                creds[key.strip()] = val.strip()
    
    required_keys = ["host", "port", "database", "user", "password"]
    for k in required_keys:
        if k not in creds:
            raise KeyError(f"Missing required key '{k}' in {env_path}")
            
    return creds


def get_connection(creds):
    """Create and return a psycopg2 database connection."""
    print(f"Connecting to database '{creds['database']}' on host '{creds['host']}' (user: '{creds['user']}')...")
    conn = psycopg2.connect(
        host=creds["host"],
        port=int(creds["port"]),
        database=creds["database"],
        user=creds["user"],
        password=creds["password"]
    )
    conn.autocommit = False
    return conn


def create_schema(cursor):
    """Drop and recreate all star schema tables and indexes in public schema."""
    print("\n--- 1. Dropping existing tables (if any) and creating Star Schema ---")
    
    drop_sql = """
    DROP TABLE IF EXISTS fact_sales CASCADE;
    DROP TABLE IF EXISTS dim_customer CASCADE;
    DROP TABLE IF EXISTS dim_product CASCADE;
    DROP TABLE IF EXISTS dim_geography CASCADE;
    DROP TABLE IF EXISTS dim_ship_mode CASCADE;
    DROP TABLE IF EXISTS dim_date CASCADE;
    """
    cursor.execute(drop_sql)

    ddl_sql = """
    -- Dimension: Customer
    CREATE TABLE dim_customer (
        customer_key SERIAL PRIMARY KEY,
        customer_id VARCHAR(50) NOT NULL UNIQUE,
        customer_name VARCHAR(255) NOT NULL,
        segment VARCHAR(50) NOT NULL
    );

    -- Dimension: Product
    CREATE TABLE dim_product (
        product_key SERIAL PRIMARY KEY,
        product_id VARCHAR(50) NOT NULL,
        product_name TEXT NOT NULL,
        category VARCHAR(100) NOT NULL,
        sub_category VARCHAR(100) NOT NULL,
        CONSTRAINT uq_dim_product_natural_key UNIQUE (product_id, product_name)
    );

    -- Dimension: Geography
    CREATE TABLE dim_geography (
        geography_key SERIAL PRIMARY KEY,
        country VARCHAR(100) NOT NULL,
        region VARCHAR(100) NOT NULL,
        state VARCHAR(100) NOT NULL,
        city VARCHAR(100) NOT NULL,
        postal_code VARCHAR(20) NOT NULL,
        CONSTRAINT uq_dim_geography_natural_key UNIQUE (country, state, city, postal_code)
    );

    -- Dimension: Ship Mode
    CREATE TABLE dim_ship_mode (
        ship_mode_key SERIAL PRIMARY KEY,
        ship_mode VARCHAR(50) NOT NULL UNIQUE
    );

    -- Dimension: Date (Role-playing dimension for Order Date and Ship Date)
    CREATE TABLE dim_date (
        date_key SERIAL PRIMARY KEY,
        date DATE NOT NULL UNIQUE,
        year INT NOT NULL,
        quarter INT NOT NULL,
        month INT NOT NULL,
        month_name VARCHAR(20) NOT NULL,
        day INT NOT NULL,
        day_of_week VARCHAR(20) NOT NULL
    );

    -- Fact: Sales
    CREATE TABLE fact_sales (
        sales_key SERIAL PRIMARY KEY,
        row_id INT NOT NULL UNIQUE,
        order_id VARCHAR(50) NOT NULL,
        customer_key INT NOT NULL REFERENCES dim_customer(customer_key),
        product_key INT NOT NULL REFERENCES dim_product(product_key),
        geography_key INT NOT NULL REFERENCES dim_geography(geography_key),
        ship_mode_key INT NOT NULL REFERENCES dim_ship_mode(ship_mode_key),
        order_date_key INT NOT NULL REFERENCES dim_date(date_key),
        ship_date_key INT NOT NULL REFERENCES dim_date(date_key),
        sales NUMERIC(12, 4) NOT NULL,
        quantity INT NOT NULL,
        discount NUMERIC(6, 4) NOT NULL,
        profit NUMERIC(12, 4) NOT NULL
    );

    -- Indexes on foreign key columns for optimal join performance
    CREATE INDEX idx_fact_sales_customer_key ON fact_sales(customer_key);
    CREATE INDEX idx_fact_sales_product_key ON fact_sales(product_key);
    CREATE INDEX idx_fact_sales_geography_key ON fact_sales(geography_key);
    CREATE INDEX idx_fact_sales_ship_mode_key ON fact_sales(ship_mode_key);
    CREATE INDEX idx_fact_sales_order_date_key ON fact_sales(order_date_key);
    CREATE INDEX idx_fact_sales_ship_date_key ON fact_sales(ship_date_key);
    """
    cursor.execute(ddl_sql)
    print("Star schema tables and indexes created successfully.")


def load_data(conn, csv_path="data/Sample - Superstore.csv"):
    """Extract CSV, transform dimensions & facts, and load into Postgres."""
    print(f"\n--- 2. Reading CSV dataset from '{csv_path}' (latin-1) ---")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    # Read CSV with latin-1 encoding
    df = pd.read_csv(csv_path, encoding="latin-1", dtype={"Postal Code": str})
    print(f"Loaded CSV with {len(df):,} rows and {len(df.columns)} columns.")

    # Parse dates from M/D/YYYY
    df["Order Date Parsed"] = pd.to_datetime(df["Order Date"], format="%m/%d/%Y").dt.date
    df["Ship Date Parsed"] = pd.to_datetime(df["Ship Date"], format="%m/%d/%Y").dt.date

    cur = conn.cursor()

    # --- Load dim_date ---
    print("\n--- 3. Loading Dimensions ---")
    all_dates = pd.concat([pd.Series(df["Order Date Parsed"]), pd.Series(df["Ship Date Parsed"])]).drop_duplicates().sort_values()
    
    date_records = []
    for dt in all_dates:
        # Convert date to datetime to extract attributes
        dt_obj = pd.Timestamp(dt)
        date_records.append((
            dt,
            int(dt_obj.year),
            int(dt_obj.quarter),
            int(dt_obj.month),
            str(dt_obj.strftime("%B")),
            int(dt_obj.day),
            str(dt_obj.strftime("%A"))
        ))
    
    insert_date_sql = """
    INSERT INTO dim_date (date, year, quarter, month, month_name, day, day_of_week)
    VALUES %s
    """
    execute_values(cur, insert_date_sql, date_records, page_size=1000)
    
    # In-memory mapping for dim_date
    cur.execute("SELECT date_key, date FROM dim_date;")
    date_map = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Loaded dim_date: {len(date_map):,} rows")

    # --- Load dim_customer ---
    cust_df = df[["Customer ID", "Customer Name", "Segment"]].drop_duplicates(subset=["Customer ID"])
    cust_records = [
        (row["Customer ID"], row["Customer Name"], row["Segment"])
        for _, row in cust_df.iterrows()
    ]
    insert_cust_sql = """
    INSERT INTO dim_customer (customer_id, customer_name, segment)
    VALUES %s
    """
    execute_values(cur, insert_cust_sql, cust_records, page_size=1000)
    
    # In-memory mapping for dim_customer
    cur.execute("SELECT customer_key, customer_id FROM dim_customer;")
    cust_map = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Loaded dim_customer: {len(cust_map):,} rows")

    # --- Load dim_product ---
    # Natural key = (Product ID, Product Name)
    prod_df = df[["Product ID", "Product Name", "Category", "Sub-Category"]].drop_duplicates(subset=["Product ID", "Product Name"])
    prod_records = [
        (row["Product ID"], row["Product Name"], row["Category"], row["Sub-Category"])
        for _, row in prod_df.iterrows()
    ]
    insert_prod_sql = """
    INSERT INTO dim_product (product_id, product_name, category, sub_category)
    VALUES %s
    """
    execute_values(cur, insert_prod_sql, prod_records, page_size=1000)
    
    # In-memory mapping for dim_product
    cur.execute("SELECT product_key, product_id, product_name FROM dim_product;")
    prod_map = {(row[1], row[2]): row[0] for row in cur.fetchall()}
    print(f"Loaded dim_product: {len(prod_map):,} rows")

    # --- Load dim_geography ---
    # Natural key = (country, state, city, postal_code)
    geo_df = df[["Country", "Region", "State", "City", "Postal Code"]].drop_duplicates(subset=["Country", "State", "City", "Postal Code"])
    geo_records = [
        (row["Country"], row["Region"], row["State"], row["City"], str(row["Postal Code"]))
        for _, row in geo_df.iterrows()
    ]
    insert_geo_sql = """
    INSERT INTO dim_geography (country, region, state, city, postal_code)
    VALUES %s
    """
    execute_values(cur, insert_geo_sql, geo_records, page_size=1000)
    
    # In-memory mapping for dim_geography
    cur.execute("SELECT geography_key, country, state, city, postal_code FROM dim_geography;")
    geo_map = {(row[1], row[2], row[3], row[4]): row[0] for row in cur.fetchall()}
    print(f"Loaded dim_geography: {len(geo_map):,} rows")

    # --- Load dim_ship_mode ---
    ship_df = df[["Ship Mode"]].drop_duplicates()
    ship_records = [(row["Ship Mode"],) for _, row in ship_df.iterrows()]
    insert_ship_sql = """
    INSERT INTO dim_ship_mode (ship_mode)
    VALUES %s
    """
    execute_values(cur, insert_ship_sql, ship_records, page_size=1000)
    
    # In-memory mapping for dim_ship_mode
    cur.execute("SELECT ship_mode_key, ship_mode FROM dim_ship_mode;")
    ship_map = {row[1]: row[0] for row in cur.fetchall()}
    print(f"Loaded dim_ship_mode: {len(ship_map):,} rows")

    # --- Load fact_sales ---
    print("\n--- 4. Resolving Keys and Loading fact_sales ---")
    fact_records = []
    for _, row in df.iterrows():
        c_key = cust_map[row["Customer ID"]]
        p_key = prod_map[(row["Product ID"], row["Product Name"])]
        g_key = geo_map[(row["Country"], row["State"], row["City"], str(row["Postal Code"]))]
        s_key = ship_map[row["Ship Mode"]]
        od_key = date_map[row["Order Date Parsed"]]
        sd_key = date_map[row["Ship Date Parsed"]]
        
        fact_records.append((
            int(row["Row ID"]),
            str(row["Order ID"]),
            c_key,
            p_key,
            g_key,
            s_key,
            od_key,
            sd_key,
            float(row["Sales"]),
            int(row["Quantity"]),
            float(row["Discount"]),
            float(row["Profit"])
        ))

    insert_fact_sql = """
    INSERT INTO fact_sales (
        row_id,
        order_id,
        customer_key,
        product_key,
        geography_key,
        ship_mode_key,
        order_date_key,
        ship_date_key,
        sales,
        quantity,
        discount,
        profit
    )
    VALUES %s
    """
    execute_values(cur, insert_fact_sql, fact_records, page_size=2000)
    print(f"Loaded fact_sales: {len(fact_records):,} rows inserted.")

    # Commit all changes
    conn.commit()
    cur.close()
    print("All transactions committed successfully.")


def validate(conn):
    """Run validation checks and sanity join query."""
    print("\n" + "=" * 60)
    print("                    VALIDATION REPORT")
    print("=" * 60)
    
    cur = conn.cursor()
    
    tables = [
        "dim_customer",
        "dim_product",
        "dim_geography",
        "dim_ship_mode",
        "dim_date",
        "fact_sales"
    ]
    
    print("\n[Table Row Counts]")
    print(f"{'Table Name':<20} | {'Row Count':>10}")
    print("-" * 35)
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        count = cur.fetchone()[0]
        print(f"{table:<20} | {count:>10,}")

    print("\n[Sanity Join: Sales, Profit & Quantity by Product Category]")
    sanity_sql = """
    SELECT 
        p.category,
        COUNT(f.sales_key) AS order_lines,
        SUM(f.quantity) AS total_quantity,
        ROUND(SUM(f.sales), 2) AS total_sales,
        ROUND(SUM(f.profit), 2) AS total_profit,
        ROUND((SUM(f.profit) / NULLIF(SUM(f.sales), 0) * 100), 2) AS profit_margin_pct
    FROM fact_sales f
    JOIN dim_product p ON f.product_key = p.product_key
    GROUP BY p.category
    ORDER BY total_sales DESC;
    """
    cur.execute(sanity_sql)
    results = cur.fetchall()
    
    print(f"{'Category':<18} | {'Order Lines':>12} | {'Total Qty':>10} | {'Total Sales ($)':>16} | {'Total Profit ($)':>16} | {'Margin %':>10}")
    print("-" * 95)
    for row in results:
        print(f"{row[0]:<18} | {row[1]:>12,} | {row[2]:>10,} | {row[3]:>16,.2f} | {row[4]:>16,.2f} | {row[5]:>9.2f}%")

    print("\n[Sanity Join: Sales by Region and Customer Segment]")
    sanity_sql_2 = """
    SELECT 
        g.region,
        c.segment,
        COUNT(f.sales_key) AS order_lines,
        ROUND(SUM(f.sales), 2) AS total_sales,
        ROUND(SUM(f.profit), 2) AS total_profit
    FROM fact_sales f
    JOIN dim_geography g ON f.geography_key = g.geography_key
    JOIN dim_customer c ON f.customer_key = c.customer_key
    GROUP BY g.region, c.segment
    ORDER BY g.region, total_sales DESC;
    """
    cur.execute(sanity_sql_2)
    results_2 = cur.fetchall()
    
    print(f"\n{'Region':<12} | {'Segment':<15} | {'Order Lines':>12} | {'Total Sales ($)':>16} | {'Total Profit ($)':>16}")
    print("-" * 80)
    for row in results_2:
        print(f"{row[0]:<12} | {row[1]:<15} | {row[2]:>12,} | {row[3]:>16,.2f} | {row[4]:>16,.2f}")

    # Check overall totals
    cur.execute("SELECT SUM(sales), SUM(profit), SUM(quantity) FROM fact_sales;")
    totals = cur.fetchone()
    print("-" * 80)
    print(f"OVERALL TOTALS -> Sales: ${totals[0]:,.2f} | Profit: ${totals[1]:,.2f} | Quantity: {totals[2]:,}")
    print("=" * 60)
    print("Validation passed successfully!\n")

    cur.close()


def main():
    try:
        creds = load_env()
        conn = get_connection(creds)
        
        with conn.cursor() as cur:
            create_schema(cur)
        conn.commit()
        
        load_data(conn)
        validate(conn)
        
        conn.close()
        print("Star schema build and load completed successfully.")
    except Exception as e:
        print(f"\nError occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
