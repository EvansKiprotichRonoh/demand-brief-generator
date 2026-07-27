"""
Generate a realistic, self-created sample dataset so the app runs offline.
Mirrors the shape of the public "Superstore" retail dataset (Kaggle).
Run:  python make_sample_data.py
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

N = 2500
regions = ["West", "East", "Central", "South"]
categories = ["Technology", "Office Supplies", "Furniture"]
segments = ["Consumer", "Corporate", "Home Office"]

dates = pd.to_datetime("2024-01-01") + pd.to_timedelta(
    rng.integers(0, 545, size=N), unit="D"
)

# Region weights create a realistic concentration (West dominates).
region = rng.choice(regions, size=N, p=[0.42, 0.26, 0.18, 0.14])
category = rng.choice(categories, size=N, p=[0.4, 0.35, 0.25])
segment = rng.choice(segments, size=N, p=[0.5, 0.3, 0.2])

base = {"Technology": 450, "Office Supplies": 90, "Furniture": 320}
sales = np.array([rng.gamma(2.0, base[c] / 2.0) for c in category])

# Add an upward time trend + a demand spike in Nov-2024 (holiday season).
month_index = (dates.year - 2024) * 12 + dates.month
sales = sales * (1 + 0.015 * (month_index - month_index.min()))
holiday = ((dates.year == 2024) & (dates.month == 11)).astype(float)
sales = sales * (1 + 0.6 * holiday)

quantity = rng.integers(1, 8, size=N)
discount = rng.choice([0, 0.1, 0.2, 0.3], size=N, p=[0.55, 0.25, 0.15, 0.05])
# Profit correlates with sales but is eroded by discount.
profit = sales * (0.28 - 0.5 * discount) + rng.normal(0, 15, size=N)

df = pd.DataFrame(
    {
        "Order Date": dates.strftime("%Y-%m-%d"),
        "Region": region,
        "Category": category,
        "Segment": segment,
        "Sales": sales.round(2),
        "Quantity": quantity,
        "Discount": discount,
        "Profit": profit.round(2),
    }
).sort_values("Order Date")

df.to_csv("sample_sales.csv", index=False)
print(f"Wrote sample_sales.csv with {len(df):,} rows")
