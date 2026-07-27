"""
Decision Brief Generator — Streamlit UI
========================================
Upload any CSV (or use the bundled sample). The app auto-profiles the data,
computes verified facts, and generates an executive decision brief:
TL;DR + 3 key takeaways + recommended actions. Works fully offline; if an
OPENAI_API_KEY is set it will additionally write an LLM narrative.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from brief_engine import analyze, generate_brief, profile_dataframe
from llm import generate_brief_llm, llm_available

st.set_page_config(page_title="Demand Brief Generator", page_icon="📦", layout="wide")

st.title("📦 Demand Brief Generator")
st.caption(
    "Turn raw demand data into a weekly S&OP brief: forecast accuracy & bias, "
    "demand variability, inventory risk (stockout vs waste), and the actions to "
    "take. Code computes the numbers; AI writes the narrative."
)

# --------------------------------------------------------------------------- #
# Data input
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("1 · Data")
    uploaded = st.file_uploader("Upload a CSV", type=["csv"])
    use_sample = st.checkbox("Use bundled sample (q-commerce demand)", value=uploaded is None)

if uploaded is not None:
    df = pd.read_csv(uploaded)
elif use_sample and os.path.exists("sample_demand.csv"):
    df = pd.read_csv("sample_demand.csv")
else:
    st.info("⬅️ Upload a CSV or tick 'Use bundled sample' to begin.")
    st.stop()

prof = profile_dataframe(df)

# --------------------------------------------------------------------------- #
# Column mapping (auto-detected, user-overridable)
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("2 · Columns")
    date_col = st.selectbox(
        "Date column", ["(none)"] + prof.date_cols,
        index=1 if prof.date_cols else 0,
    )
    metric_col = st.selectbox(
        "Metric to analyse", prof.numeric_cols,
        index=0 if prof.numeric_cols else None,
    )
    dimension_col = st.selectbox(
        "Segment / dimension", ["(none)"] + prof.categorical_cols,
        index=1 if prof.categorical_cols else 0,
    )
    st.header("3 · Narrative")
    st.write("🟢 LLM available" if llm_available() else "⚪ LLM off (deterministic mode)")

date_col = None if date_col == "(none)" else date_col
dimension_col = None if dimension_col == "(none)" else dimension_col

# --------------------------------------------------------------------------- #
# Analyse + generate
# --------------------------------------------------------------------------- #
facts = analyze(df, date_col=date_col, metric_col=metric_col, dimension_col=dimension_col)
brief = generate_brief(facts)

if brief.get("error"):
    st.error(brief["error"])
    st.stop()

# ---- demand KPIs (only shown when demand-planning columns are detected) ----
dm = facts.get("demand", {})
if facts.get("is_demand") and dm:
    k1, k2, k3, k4 = st.columns(4)
    if dm.get("accuracy_pct") is not None:
        k1.metric("Forecast accuracy", f"{dm['accuracy_pct']:.0f}%",
                  help="100 − WMAPE (weighted MAPE) vs actual demand")
    if dm.get("bias_pct") is not None:
        k2.metric("Forecast bias", f"{dm['bias_pct']:+.0f}%",
                  help="Positive = over-forecast (waste); negative = under-forecast (stockouts)")
    if dm.get("days_of_cover") is not None:
        k3.metric("Days of cover", f"{dm['days_of_cover']:.1f}")
    if dm.get("promo_uplift_pct") is not None:
        k4.metric("Promo uplift", f"{dm['promo_uplift_pct']:.0f}%")

col_brief, col_data = st.columns([3, 2])

with col_brief:
    st.subheader("Executive Decision Brief")
    llm_md = generate_brief_llm(facts) if llm_available() else None
    if llm_md:
        st.markdown(llm_md)
        with st.expander("Deterministic version (fallback)"):
            st.markdown(brief["markdown"])
    else:
        st.markdown(brief["markdown"])

    st.download_button(
        "⬇️ Download brief (Markdown)",
        data=(llm_md or brief["markdown"]),
        file_name="decision_brief.md",
        mime="text/markdown",
    )

with col_data:
    st.subheader("What the tool saw")
    # Forecast vs actual over time (the demand planner's core chart)
    roles = facts.get("demand_roles", {})
    a_col, f_col, d_col = roles.get("actual"), roles.get("forecast"), roles.get("date")
    if facts.get("is_demand") and a_col and f_col and d_col:
        tmp = df[[d_col]].copy()
        tmp["_d"] = pd.to_datetime(df[d_col], errors="coerce", format="mixed")
        tmp["Actual"] = pd.to_numeric(df[a_col], errors="coerce")
        tmp["Forecast"] = pd.to_numeric(df[f_col], errors="coerce")
        wk = tmp.dropna(subset=["_d"]).set_index("_d")[["Actual", "Forecast"]].resample("W").sum()
        st.markdown("**Actual vs Forecast** (weekly)")
        st.line_chart(wk)
    elif facts.get("series"):
        ts = pd.Series(facts["series"])
        ts.index = pd.to_datetime(ts.index)
        st.markdown(f"**{facts['metric_col']} over time** (by {facts.get('period','period')})")
        st.line_chart(ts)
    if facts.get("segment_breakdown"):
        st.markdown(f"**{facts['metric_col']} by {facts['dimension_col']}**")
        st.bar_chart(pd.Series(facts["segment_breakdown"]))

with st.expander("Preview data & verified facts"):
    st.dataframe(df.head(50), width="stretch")
    st.json({k: v for k, v in facts.items() if k not in ("series", "segment_breakdown")})
