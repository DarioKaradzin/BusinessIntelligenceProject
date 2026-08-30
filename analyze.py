import os
import pandas as pd

csv_path = r"C:\projects\my-workspace\data\Sample - Superstore.csv"

if not os.path.exists(csv_path):
    print("Error: File not found")
    exit(1)

df = pd.read_csv(csv_path, encoding='latin1')

print(f"Shape: {df.shape[0]} rows, {df.shape[1]} columns")

# Convert Order Date to datetime
df['Order Date'] = pd.to_datetime(df['Order Date'], format='%m/%d/%Y', errors='coerce')
if df['Order Date'].isnull().all():
    df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
    
min_order_date = df['Order Date'].min()
max_order_date = df['Order Date'].max()

total_sales = df['Sales'].sum()
total_profit = df['Profit'].sum()
total_quantity = df['Quantity'].sum()
overall_margin = (total_profit / total_sales) * 100 if total_sales else 0

print(f"Date Range: {min_order_date.strftime('%Y-%m-%d') if pd.notnull(min_order_date) else 'N/A'} to {max_order_date.strftime('%Y-%m-%d') if pd.notnull(max_order_date) else 'N/A'}")
print(f"Total Sales: ${total_sales:,.2f}")
print(f"Total Profit: ${total_profit:,.2f}")
print(f"Total Quantity Sold: {total_quantity:,}")
print(f"Overall Profit Margin: {overall_margin:.2f}%")

print("\n--- Sales & Profit by Category ---")
cat_summary = df.groupby('Category').agg(
    Sales=('Sales', 'sum'),
    Profit=('Profit', 'sum'),
    Quantity=('Quantity', 'sum')
).reset_index()
cat_summary['Margin %'] = (cat_summary['Profit'] / cat_summary['Sales']) * 100
print(cat_summary.to_string(index=False))

print("\n--- Top 5 Sub-Categories by Sales ---")
subcat_summary = df.groupby('Sub-Category').agg(
    Sales=('Sales', 'sum'),
    Profit=('Profit', 'sum')
).reset_index().sort_values(by='Sales', ascending=False).head(5)
print(subcat_summary.to_string(index=False))

print("\n--- Top 5 States by Sales ---")
state_summary = df.groupby('State').agg(
    Sales=('Sales', 'sum'),
    Profit=('Profit', 'sum')
).reset_index().sort_values(by='Sales', ascending=False).head(5)
print(state_summary.to_string(index=False))

print("\n--- Top 5 Customers by Sales ---")
cust_summary = df.groupby(['Customer ID', 'Customer Name']).agg(
    Sales=('Sales', 'sum'),
    Profit=('Profit', 'sum')
).reset_index().sort_values(by='Sales', ascending=False).head(5)
print(cust_summary.to_string(index=False))

print("\n--- Segment Breakdown ---")
seg_summary = df.groupby('Segment').agg(
    Sales=('Sales', 'sum'),
    Profit=('Profit', 'sum'),
    Percent_Sales=('Sales', lambda x: (x.sum() / total_sales) * 100)
).reset_index()
print(seg_summary.to_string(index=False))

print("\n--- Region Breakdown ---")
region_summary = df.groupby('Region').agg(
    Sales=('Sales', 'sum'),
    Profit=('Profit', 'sum')
).reset_index()
print(region_summary.to_string(index=False))
