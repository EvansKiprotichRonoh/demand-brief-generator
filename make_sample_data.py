"""
Generate a realistic quick-commerce (dark store) demand-planning dataset so the
app runs offline. Shaped for demand planning / S&OP: actuals vs forecast,
on-hand inventory, promos, seasonality — by SKU, category and dark store.

Run:  python make_sample_data.py
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)

stores = [
    "DS-Amsterdam-01", "DS-Amsterdam-02", "DS-Rotterdam-01",
    "DS-Utrecht-01", "DS-TheHague-01",
]
categories = {
    "Fresh Produce": 40,   # perishable -> waste risk if over-forecast
    "Dairy": 32,
    "Beverages": 55,
    "Snacks": 48,
    "Household": 22,
}
skus_per_cat = 6

# Build a SKU catalogue.
catalogue = []
for cat, base in categories.items():
    for i in range(skus_per_cat):
        catalogue.append((f"{cat[:3].upper()}-{i+1:02d}", cat, base))

dates = pd.date_range("2025-01-01", "2025-03-31", freq="D")

rows = []
for d in dates:
    dow = d.dayofweek
    weekend_lift = 1.35 if dow >= 5 else 1.0
    # gentle upward trend over the quarter
    trend = 1 + 0.004 * (d - dates[0]).days
    for store in stores:
        store_factor = rng.uniform(0.8, 1.25)
        for sku, cat, base in catalogue:
            promo = 1 if rng.random() < 0.08 else 0
            promo_lift = 1.8 if promo else 1.0
            mean_demand = base * weekend_lift * trend * store_factor * promo_lift
            units = int(max(0, rng.poisson(mean_demand)))

            # Forecast has category-specific bias to create variance-analysis signal:
            #  - Fresh Produce is systematically OVER-forecast (-> waste)
            #  - Snacks is systematically UNDER-forecast (-> stockouts)
            bias = {"Fresh Produce": 1.18, "Snacks": 0.85}.get(cat, 1.0)
            noise = rng.normal(1.0, 0.12)
            forecast = int(max(0, mean_demand * bias * noise))

            # On-hand inventory: some stores run thin on Snacks, fat on Produce.
            cover_days = {"Fresh Produce": 6.0, "Snacks": 1.5}.get(cat, 3.5)
            on_hand = int(max(0, units * cover_days * rng.uniform(0.8, 1.2)))

            rows.append(
                {
                    "Date": d.strftime("%Y-%m-%d"),
                    "Dark_Store": store,
                    "Category": cat,
                    "SKU": sku,
                    "Units_Sold": units,
                    "Forecast_Units": forecast,
                    "On_Hand_Units": on_hand,
                    "Promo_Flag": promo,
                }
            )

df = pd.DataFrame(rows)
df.to_csv("sample_demand.csv", index=False)
print(f"Wrote sample_demand.csv with {len(df):,} rows "
      f"({df['SKU'].nunique()} SKUs x {df['Dark_Store'].nunique()} stores x "
      f"{df['Date'].nunique()} days)")
