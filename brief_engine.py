"""
brief_engine.py
----------------
The analytical core of the Decision Brief Generator.

Given *any* tabular dataset (CSV / DataFrame), this module:
  1. Profiles the data (dates, numeric metrics, categorical dimensions).
  2. Computes facts: trends, period-over-period growth, top/bottom segments,
     concentration, anomalies and correlations.
  3. Turns those facts into an executive decision brief:
        - a one-line TL;DR
        - exactly 3 key takeaways
        - concrete recommended business actions

It is deliberately dependency-light (pandas + numpy) and has **no** hard
dependency on Streamlit or any LLM, so it can run anywhere and is easy to test.
An optional LLM narrative layer lives in `llm.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Profiling
# --------------------------------------------------------------------------- #
@dataclass
class Profile:
    date_cols: list[str] = field(default_factory=list)
    numeric_cols: list[str] = field(default_factory=list)
    categorical_cols: list[str] = field(default_factory=list)
    n_rows: int = 0
    n_cols: int = 0


def _looks_like_date(series: pd.Series) -> bool:
    """Heuristic: can a decent fraction of the column be parsed as dates?"""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_numeric_dtype(series):
        return False
    sample = series.dropna().astype(str).head(50)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return parsed.notna().mean() >= 0.7


def profile_dataframe(df: pd.DataFrame) -> Profile:
    prof = Profile(n_rows=len(df), n_cols=df.shape[1])
    for col in df.columns:
        s = df[col]
        if _looks_like_date(s):
            prof.date_cols.append(col)
        elif pd.api.types.is_numeric_dtype(s):
            prof.numeric_cols.append(col)
        else:
            # low-ish cardinality object columns make good dimensions
            nunique = s.nunique(dropna=True)
            if nunique <= max(50, int(0.5 * len(df))):
                prof.categorical_cols.append(col)
    return prof


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def _pct(a: float, b: float) -> float | None:
    """Percent change from b -> a, guarding divide-by-zero."""
    if b in (0, None) or pd.isna(b):
        return None
    return (a - b) / abs(b) * 100.0


def _fmt_num(x: float) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    ax = abs(x)
    if ax >= 1_000_000_000:
        return f"{x/1_000_000_000:.2f}B"
    if ax >= 1_000_000:
        return f"{x/1_000_000:.2f}M"
    if ax >= 1_000:
        return f"{x/1_000:.1f}K"
    if ax >= 1:
        return f"{x:,.1f}"
    return f"{x:.3f}"


def analyze(
    df: pd.DataFrame,
    date_col: str | None = None,
    metric_col: str | None = None,
    dimension_col: str | None = None,
) -> dict[str, Any]:
    """Compute a structured 'facts' dictionary from the dataframe."""
    prof = profile_dataframe(df)

    # ---- pick sensible defaults if the caller did not specify ----
    if date_col is None and prof.date_cols:
        date_col = prof.date_cols[0]
    if metric_col is None and prof.numeric_cols:
        # prefer the highest-variance numeric column as the "headline" metric
        variances = {c: df[c].astype(float).var(skipna=True) for c in prof.numeric_cols}
        metric_col = max(variances, key=lambda k: (variances[k] or 0))
    if dimension_col is None and prof.categorical_cols:
        dimension_col = prof.categorical_cols[0]

    facts: dict[str, Any] = {
        "profile": prof.__dict__,
        "date_col": date_col,
        "metric_col": metric_col,
        "dimension_col": dimension_col,
        "findings": [],
    }
    if metric_col is None:
        facts["error"] = "No numeric metric column found to analyse."
        return facts

    metric = pd.to_numeric(df[metric_col], errors="coerce")
    facts["metric_total"] = float(metric.sum(skipna=True))
    facts["metric_mean"] = float(metric.mean(skipna=True))
    facts["metric_median"] = float(metric.median(skipna=True))

    # ---- time trend ----
    if date_col is not None:
        d = df.copy()
        d["_date"] = pd.to_datetime(d[date_col], errors="coerce", format="mixed")
        d["_metric"] = metric.values
        d = d.dropna(subset=["_date"])
        if not d.empty:
            span_days = (d["_date"].max() - d["_date"].min()).days
            freq = "W" if span_days <= 120 else "ME"  # month-end for long spans
            ts = (
                d.set_index("_date")["_metric"]
                .resample(freq)
                .sum()
                .dropna()
            )
            facts["series"] = {str(k.date()): float(v) for k, v in ts.items()}
            facts["period"] = "week" if freq == "W" else "month"

            if len(ts) >= 2:
                latest, prev = ts.iloc[-1], ts.iloc[-2]
                pop = _pct(latest, prev)
                facts["pop_change_pct"] = pop
                facts["latest_period_value"] = float(latest)
                if pop is not None:
                    direction = "up" if pop >= 0 else "down"
                    facts["findings"].append(
                        f"{metric_col} is {direction} {abs(pop):.1f}% "
                        f"in the latest {facts['period']} "
                        f"({_fmt_num(prev)} → {_fmt_num(latest)})."
                    )
                # overall trend across the window
                first, last = ts.iloc[0], ts.iloc[-1]
                overall = _pct(last, first)
                facts["overall_change_pct"] = overall
                if overall is not None:
                    trend = "grown" if overall >= 0 else "declined"
                    facts["findings"].append(
                        f"Across the full window {metric_col} has {trend} "
                        f"{abs(overall):.1f}% ({_fmt_num(first)} → {_fmt_num(last)})."
                    )
                # anomaly detection on the periodic series (z-score)
                mu, sigma = ts.mean(), ts.std(ddof=0)
                if sigma and sigma > 0:
                    z = (ts - mu) / sigma
                    spikes = z[abs(z) >= 2.0]
                    if not spikes.empty:
                        worst = spikes.abs().idxmax()
                        facts["anomaly"] = {
                            "period": str(worst.date()),
                            "value": float(ts[worst]),
                            "z": float(z[worst]),
                        }
                        facts["findings"].append(
                            f"Unusual {facts['period']} on {worst.date()}: "
                            f"{_fmt_num(ts[worst])} "
                            f"({z[worst]:+.1f}σ from the mean) — worth investigating."
                        )

    # ---- segment / dimension analysis ----
    if dimension_col is not None:
        g = (
            df.assign(_m=metric)
            .groupby(dimension_col)["_m"]
            .sum()
            .sort_values(ascending=False)
        )
        g = g[g.notna()]
        if not g.empty:
            total = g.sum()
            top_name, top_val = g.index[0], g.iloc[0]
            bot_name, bot_val = g.index[-1], g.iloc[-1]
            top_share = (top_val / total * 100.0) if total else None
            facts["top_segment"] = {"name": str(top_name), "value": float(top_val),
                                    "share_pct": top_share}
            facts["bottom_segment"] = {"name": str(bot_name), "value": float(bot_val)}
            facts["segment_breakdown"] = {str(k): float(v) for k, v in g.head(10).items()}
            if top_share is not None:
                facts["findings"].append(
                    f"'{top_name}' is the leading {dimension_col}, contributing "
                    f"{_fmt_num(top_val)} of {metric_col} ({top_share:.0f}% of total)."
                )
            # concentration risk
            if top_share is not None and top_share >= 40:
                facts["findings"].append(
                    f"Revenue concentration risk: the single {dimension_col} "
                    f"'{top_name}' accounts for {top_share:.0f}% of {metric_col}."
                )
            facts["findings"].append(
                f"Weakest {dimension_col}: '{bot_name}' at {_fmt_num(bot_val)} "
                f"{metric_col} — a candidate for review or divestment."
            )

    # ---- correlation between numeric metrics ----
    nums = [c for c in prof.numeric_cols if c != metric_col]
    if nums:
        corr = df[[metric_col] + nums].apply(pd.to_numeric, errors="coerce").corr()
        if metric_col in corr:
            rel = corr[metric_col].drop(labels=[metric_col]).dropna()
            if not rel.empty:
                strongest = rel.abs().idxmax()
                r = rel[strongest]
                if abs(r) >= 0.5:
                    kind = "positively" if r > 0 else "negatively"
                    facts["correlation"] = {"with": strongest, "r": float(r)}
                    facts["findings"].append(
                        f"{metric_col} is strongly {kind} correlated with "
                        f"{strongest} (r = {r:+.2f}) — a potential lever."
                    )

    return facts


# --------------------------------------------------------------------------- #
# Brief generation (deterministic, no-LLM fallback)
# --------------------------------------------------------------------------- #
def _recommend_actions(facts: dict[str, Any]) -> list[str]:
    """Map computed findings to concrete business actions (rule-based)."""
    actions: list[str] = []
    metric = facts.get("metric_col", "the metric")

    pop = facts.get("pop_change_pct")
    if pop is not None:
        if pop < -5:
            actions.append(
                f"Convene a review of the recent {abs(pop):.0f}% drop in {metric}; "
                "identify the driver before the next reporting cycle."
            )
        elif pop > 10:
            actions.append(
                f"Double down on what drove the {pop:.0f}% lift in {metric} — "
                "protect and scale the winning channel/segment."
            )

    top = facts.get("top_segment")
    if top and top.get("share_pct") and top["share_pct"] >= 40:
        actions.append(
            f"De-risk over-reliance on '{top['name']}' "
            f"({top['share_pct']:.0f}% of {metric}) by growing the next-tier segments."
        )

    bot = facts.get("bottom_segment")
    if bot:
        actions.append(
            f"Decide fix-or-cut for the underperforming '{bot['name']}' segment "
            "within the quarter."
        )

    if facts.get("anomaly"):
        a = facts["anomaly"]
        actions.append(
            f"Root-cause the anomaly on {a['period']} "
            f"({a['z']:+.1f}σ) and add a monitoring alert to catch repeats."
        )

    corr = facts.get("correlation")
    if corr:
        actions.append(
            f"Run a controlled test on '{corr['with']}' (r={corr['r']:+.2f} with {metric}) "
            "to confirm it as a growth lever."
        )

    if not actions:
        actions.append(
            f"Establish a weekly tracking cadence for {metric} and set a target "
            "so future briefs can measure progress against a baseline."
        )
    return actions[:4]


def generate_brief(facts: dict[str, Any]) -> dict[str, Any]:
    """Produce the structured brief + a markdown rendering from the facts."""
    if facts.get("error"):
        return {"error": facts["error"]}

    metric = facts["metric_col"]
    findings = facts.get("findings", [])
    takeaways = findings[:3] if findings else [
        f"Analysed {facts['profile']['n_rows']:,} rows across "
        f"{facts['profile']['n_cols']} columns; {metric} totals "
        f"{_fmt_num(facts.get('metric_total'))}."
    ]

    # TL;DR
    pieces = [f"Total {metric} of {_fmt_num(facts.get('metric_total'))}"]
    if facts.get("pop_change_pct") is not None:
        arrow = "▲" if facts["pop_change_pct"] >= 0 else "▼"
        pieces.append(f"{arrow} {abs(facts['pop_change_pct']):.1f}% latest {facts.get('period','period')}")
    if facts.get("top_segment"):
        pieces.append(f"led by '{facts['top_segment']['name']}'")
    tldr = "; ".join(pieces) + "."

    actions = _recommend_actions(facts)

    brief = {
        "tldr": tldr,
        "takeaways": takeaways,
        "actions": actions,
        "action_point": actions[0] if actions else "",
    }
    brief["markdown"] = render_markdown(facts, brief)
    return brief


def render_markdown(facts: dict[str, Any], brief: dict[str, Any]) -> str:
    lines = ["# 📊 Executive Decision Brief", ""]
    lines.append(f"**TL;DR —** {brief['tldr']}")
    lines.append("")
    lines.append("## Three Key Takeaways")
    for i, t in enumerate(brief["takeaways"], 1):
        lines.append(f"{i}. {t}")
    lines.append("")
    lines.append("## Recommended Actions")
    for a in brief["actions"]:
        lines.append(f"- {a}")
    lines.append("")
    lines.append("---")
    meta = (
        f"_Basis: {facts['profile']['n_rows']:,} rows · metric = **{facts['metric_col']}**"
    )
    if facts.get("date_col"):
        meta += f" · time = **{facts['date_col']}**"
    if facts.get("dimension_col"):
        meta += f" · segment = **{facts['dimension_col']}**"
    meta += "._"
    lines.append(meta)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI entry point — lets you run:  python brief_engine.py data.csv
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sample_sales.csv"
    df_ = pd.read_csv(path)
    facts_ = analyze(df_)
    brief_ = generate_brief(facts_)
    print(brief_.get("markdown", brief_.get("error")))
