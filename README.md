# 📦 Demand Brief Generator

**▶ Live app:** https://evanskiprotichronoh-demand-brief-generator-app-w88dt6.streamlit.app/


**AI Challenge #1 — a tool that turns raw data into summaries and recommended business actions**,
tailored to a **Demand Planning / S&OP** role in quick-commerce (dark stores).
(It also fulfils Challenge #3: every brief ends in *3 key takeaways + an action point*.)

Upload **any** demand CSV → the tool auto-detects your date, SKU, store, forecast
and inventory columns and writes the **weekly S&OP brief a planner presents to leadership**:

- **Forecast accuracy & bias** — WMAPE and over/under-forecast bias, by segment (variance analysis)
- **Demand variability** — coefficient of variation → safety-stock / scenario-planning candidates
- **Inventory risk** — days-of-cover → stockout vs waste/overstock flags by store
- **Promo uplift** — measured lift so promos aren't forecast at baseline
- **Trends & anomalies** — with a partial-period guard (no fake "−88% crash" from an incomplete week)

> **Design principle: code does the math, the LLM does the narrative.**
> Numbers are computed deterministically in Python, so the AI can *never
> hallucinate a figure* — it only rephrases verified facts. With no API key the
> tool still produces the full brief, so the weekly cadence never depends on an LLM.

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python make_sample_data.py      # creates sample_demand.csv (q-commerce demand)
streamlit run app.py            # open the app in your browser
```

No LLM key needed. To also get an AI-written narrative:

```bash
export OPENAI_API_KEY=sk-...    # optional
streamlit run app.py
```

Run it headless as a pure CLI too:

```bash
python brief_engine.py sample_demand.csv        # print the brief
python export_pdf.py sample_demand.csv brief.pdf # one-page PDF
```

---

## Example output (bundled demand data)

```
📦 Weekly Demand & S&OP Brief

TL;DR — 758.5K total Units_Sold; ▲ 2.5% latest week; forecast accuracy 83% (-1% bias); 3.4 days cover.

Three Key Takeaways
1. Forecast accuracy is 83% (WMAPE 17%), with a 1% under-forecasting bias — the number to defend to the VP.
2. 'Fresh Produce' is over-forecast by 16% (driving waste/overstock).
3. 'Snacks' is under-forecast by 16% (driving stockouts / lost sales).

Recommended Actions
- Cut the forecast for 'Fresh Produce' (+16% bias) to reduce perishable waste; re-baseline on recent actuals.
- Raise the forecast + safety stock for 'Snacks' (16% under-bias) to protect availability.
- Pre-position inventory for promo SKUs at a ~80% uplift and flag promos so peaks aren't treated as noise.
```

---

## How it works

| File | Role |
|------|------|
| `brief_engine.py` | Profiling + trends/anomalies + brief assembly (pure pandas/numpy) |
| `demand_planning.py` | Demand-planning intelligence: forecast accuracy/bias, CV, days-of-cover, promo |
| `llm.py` | Optional grounded LLM narrative layer |
| `prompt.md` | The exact, reusable weekly S&OP-brief prompt (Challenge #3) |
| `app.py` | Streamlit UI (KPIs, actual-vs-forecast chart, column mapping, downloads) |
| `export_pdf.py` | One-page PDF export of the brief (deck/email ready) |
| `make_sample_data.py` | Generates the offline q-commerce demand dataset |

Pipeline: **profile → detect demand roles → analyze (facts) → generate_brief → render**.

It stays generic: on a non-demand CSV it falls back to a standard executive brief.

---

## Deploy to a public link (free)

One command (creates the repo, pushes, prints the deploy URL):

```bash
./deploy.sh <your-github-username>
```

Or manually:
1. Push this folder to a public GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io) → "New app" → pick the
   repo and `app.py`. It builds from `requirements.txt` and gives you a public URL.
3. (Optional) add `OPENAI_API_KEY` under the app's *Secrets*.

## Data

Runs on the generated `sample_demand.csv` (self-created — actuals, forecast,
on-hand inventory, promos by SKU/category/dark store). Works on any CSV with at
least one numeric column; add `Forecast_*` / `On_Hand_*` columns to unlock the
full demand-planning brief. Public alternatives: [Kaggle](https://www.kaggle.com/datasets)
retail/demand datasets or [data.gov](https://data.gov).
