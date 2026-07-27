# Submission — AI Challenge

**Challenge attempted:** #1 Decision Brief Generator (also covers #3 Insight Summary Prompt).
**Tailored to the role:** Demand Planning / S&OP for quick-commerce (dark stores).

## Deliverables
- **Prototype:** this repo — `streamlit run app.py` (works offline, no key required).
- **One-page PDF:** `python export_pdf.py` → deck/email-ready brief (also a download button in-app).
- **Prompt:** `prompt.md` — the reusable, grounded weekly S&OP-brief prompt.
- **Dataset:** self-created `sample_demand.csv` — actuals vs forecast, on-hand
  inventory, promos, seasonality by SKU / category / dark store (mirrors a real
  demand-planning table; works on any uploaded CSV).
- **Public link:** deployable to Streamlit Community Cloud in ~2 min (see README).

## What it demonstrates for this role
Forecasting sense-check (accuracy/**WMAPE** + **bias**), **demand variability** (CV →
safety-stock candidates), **inventory optimisation** (days-of-cover → stockout vs
waste), **promo uplift**, and **insight-to-narrative** — the weekly brief a planner
presents at S&OP. Code computes it in SQL-like pandas; AI writes the story.

## 100-word summary

I built a Demand Brief Generator that turns any demand dataset into a weekly S&OP
brief. Core idea: let code do the math and the LLM do the writing. Python
auto-detects SKU, store, forecast and inventory columns, then computes the
numbers a planner defends to a VP: forecast accuracy and bias (WMAPE), demand
variability, days-of-cover, and promo uplift. It flags the availability-versus-waste
trade-off — Fresh Produce over-forecast 16% (waste), Snacks under-forecast 16%
(stockouts) — and recommends re-baselining and safety-stock actions. It runs fully
offline with a deterministic fallback, upgrading to an AI narrative when a key is
present. Grounded, portable, decision-useful.
