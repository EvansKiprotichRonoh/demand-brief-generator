# 📊 Decision Brief Generator

**AI Challenge #1 — a tool that turns raw data into summaries and recommended business actions.**
(It also fulfils Challenge #3: every brief ends in *3 key takeaways + an action point*.)

Upload **any** CSV → the tool auto-detects your dates, metrics and segments,
computes verified facts (trends, period-over-period growth, top/bottom segments,
concentration risk, statistical anomalies, correlations), and writes an
**executive decision brief**.

> **Design principle: code does the math, the LLM does the narrative.**
> Numbers are computed deterministically in Python, so the AI can *never
> hallucinate a figure* — it only rephrases verified facts. If no API key is
> present, the tool still produces the full brief from those facts.

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python make_sample_data.py      # creates sample_sales.csv
streamlit run app.py            # open the app in your browser
```

No LLM key needed. To also get an AI-written narrative:

```bash
export OPENAI_API_KEY=sk-...    # optional
streamlit run app.py
```

Run it headless as a pure CLI too:

```bash
python brief_engine.py sample_sales.csv
```

---

## Example output (bundled sample data)

```
TL;DR — Total Sales of 846.7K; ▼ 4.4% latest month; led by 'West'.

Three Key Takeaways
1. Sales is down 4.4% in the latest month (49.5K → 47.3K).
2. Across the full window Sales has grown 25.3% (37.7K → 47.3K).
3. Unusual month on 2024-11-30: 67.4K (+2.7σ) — worth investigating.

Recommended Actions
- De-risk over-reliance on 'West' (43% of Sales) by growing next-tier segments.
- Decide fix-or-cut for the underperforming 'South' segment this quarter.
- Root-cause the 2024-11-30 anomaly and add a monitoring alert.
- Test 'Profit' (r=+0.95 with Sales) to confirm it as a growth lever.
```

---

## How it works

| File | Role |
|------|------|
| `brief_engine.py` | Profiling + analytics + deterministic brief (pure pandas/numpy) |
| `llm.py` | Optional grounded LLM narrative layer |
| `prompt.md` | The exact, reusable Insight-Summary prompt (Challenge #3) |
| `app.py` | Streamlit UI (charts, column mapping, downloads) |
| `make_sample_data.py` | Generates the offline sample dataset |

Pipeline: **profile → analyze (facts) → generate_brief → render**.

---

## Deploy to a public link (free)

1. Push this folder to a public GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io) → "New app" → pick the
   repo and `app.py`. It builds from `requirements.txt` and gives you a public URL.
3. (Optional) add `OPENAI_API_KEY` under the app's *Secrets*.

## Data

Runs on the generated `sample_sales.csv` (self-created, mirrors the public
**Kaggle "Sample Superstore"** schema). Works on any CSV with at least one
numeric column — e.g. datasets from [data.gov](https://data.gov) or
[Kaggle](https://www.kaggle.com/datasets).
