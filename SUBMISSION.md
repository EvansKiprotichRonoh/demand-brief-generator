# Submission — AI Challenge

**Challenge attempted:** #1 Decision Brief Generator (also covers #3 Insight Summary Prompt).

## Deliverables
- **Prototype:** this repo — `streamlit run app.py` (works offline, no key required).
- **Prompt:** `prompt.md` — the reusable grounded Insight-Summary prompt.
- **Dataset:** self-created `sample_sales.csv` (mirrors the public Kaggle
  "Sample Superstore" schema); works on any uploaded CSV.
- **Public link:** deployable to Streamlit Community Cloud in ~2 min (see README).

## 100-word summary

I built a Decision Brief Generator that turns any CSV into an executive brief.
My core idea: **let code do the math and the LLM do the writing** — Python
profiles the data and computes verified facts (period-over-period growth,
segment concentration, statistical anomalies via z-scores, correlations), then
the model narrates *only* those numbers, so it can never hallucinate a figure.
Every brief delivers a TL;DR, three quantified takeaways, and owner-ready
actions. It auto-detects date/metric/segment columns, works fully offline with a
deterministic fallback, and upgrades to an AI narrative when a key is present.
Grounded, portable, and genuinely decision-useful.
