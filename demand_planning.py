"""
demand_planning.py
------------------
Domain intelligence for a Demand Planning / S&OP context (quick-commerce /
dark stores). It auto-detects demand-planning columns and, when present,
computes the signals a demand planner actually reviews each week:

  - Forecast accuracy & bias  (variance analysis: actuals vs forecast, WMAPE, bias)
  - Demand variability        (coefficient of variation -> safety-stock candidates)
  - Inventory risk            (days-of-cover -> stockout vs waste/overstock flags)
  - Promo uplift              (measured lift from promotions)

Everything is optional and defensive: signals only appear when the data supports
them, so the tool still works on any generic CSV.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Column-role detection (by fuzzy name match)
# --------------------------------------------------------------------------- #
_KEYWORDS = {
    "actual": ["units_sold", "units sold", "actual", "demand", "sold", "qty",
               "quantity", "orders", "sales"],
    "forecast": ["forecast", "fcst", "predicted", "prediction", "plan", "planned"],
    "inventory": ["on_hand", "on hand", "onhand", "inventory", "stock", "soh"],
    "sku": ["sku", "item", "product", "material", "article"],
    "category": ["category", "categ", "department", "dept", "class", "family",
                 "subcategory", "sub-category"],
    "location": ["dark_store", "dark store", "store", "location", "site", "dc",
                 "warehouse", "hub"],
    "promo": ["promo", "promotion", "deal", "offer"],
    "date": ["date", "day", "week", "period", "order date"],
}


def _find(cols: list[str], role: str, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    for kw in _KEYWORDS[role]:
        for c in cols:
            if c in exclude:
                continue
            if kw in c.lower():
                return c
    return None


def detect_roles(df: pd.DataFrame) -> dict[str, str | None]:
    cols = list(df.columns)
    used: set[str] = set()
    roles: dict[str, str | None] = {}
    # order matters: forecast/inventory before generic 'actual' so they aren't grabbed
    for role in ["date", "sku", "category", "location", "forecast", "inventory",
                 "promo", "actual"]:
        col = _find(cols, role, exclude=used)
        roles[role] = col
        if col:
            used.add(col)
    return roles


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def _fmt_pct(x: float) -> str:
    return f"{x:.1f}%"


# --------------------------------------------------------------------------- #
# Main analysis
# --------------------------------------------------------------------------- #
def analyze_demand(df: pd.DataFrame) -> dict[str, Any]:
    roles = detect_roles(df)
    out: dict[str, Any] = {"roles": roles, "findings": [], "actions": [],
                           "metrics": {}, "is_demand": False}

    actual_c = roles.get("actual")
    fcst_c = roles.get("forecast")
    inv_c = roles.get("inventory")
    sku_c = roles.get("sku")
    loc_c = roles.get("location")
    promo_c = roles.get("promo")

    if actual_c is None:
        return out  # nothing demand-specific to say

    actual = _num(df, actual_c)

    # ------------------------------------------------------------------ #
    # 1) Forecast accuracy & bias (variance analysis)
    # ------------------------------------------------------------------ #
    if fcst_c is not None:
        out["is_demand"] = True
        fcst = _num(df, fcst_c)
        mask = actual.notna() & fcst.notna()
        a, f = actual[mask], fcst[mask]
        tot_a = a.sum()
        if tot_a > 0:
            wmape = (a - f).abs().sum() / tot_a * 100.0        # weighted MAPE
            bias = (f - a).sum() / tot_a * 100.0               # + = over-forecast
            accuracy = max(0.0, 100.0 - wmape)
            out["metrics"].update(
                {"wmape_pct": float(wmape), "bias_pct": float(bias),
                 "accuracy_pct": float(accuracy)}
            )
            lean = "over-forecasting" if bias > 0 else "under-forecasting"
            out["findings"].append(
                f"Forecast accuracy is {accuracy:.0f}% (WMAPE {wmape:.0f}%), with a "
                f"{abs(bias):.0f}% {lean} bias — this is the number to defend to the VP."
            )

            # worst-biased segment — prefer category (that's where systematic
            # over/under-forecast bias usually lives), then location, then SKU.
            cat_c = roles.get("category")
            seg_c = _pick_segment(df, [cat_c, loc_c, sku_c])
            if seg_c is not None:
                seg_df = pd.DataFrame({"a": a.values, "f": f.values,
                                       "seg": df.loc[mask, seg_c].values})
                agg = seg_df.groupby("seg")[["a", "f"]].sum()
                g = ((agg["f"] - agg["a"]) / agg["a"].clip(lower=1) * 100.0).sort_values()
                if len(g) >= 1:
                    over_seg, over_val = g.index[-1], g.iloc[-1]
                    under_seg, under_val = g.index[0], g.iloc[0]
                    if over_val > 10:
                        out["findings"].append(
                            f"'{over_seg}' is over-forecast by {over_val:.0f}% "
                            f"(driving waste/overstock)."
                        )
                        out["actions"].append(
                            f"Cut the forecast for '{over_seg}' (+{over_val:.0f}% bias) to "
                            "reduce perishable waste; re-baseline the model on recent actuals."
                        )
                    if under_val < -10:
                        out["findings"].append(
                            f"'{under_seg}' is under-forecast by {abs(under_val):.0f}% "
                            f"(driving stockouts / lost sales)."
                        )
                        out["actions"].append(
                            f"Raise the forecast + safety stock for '{under_seg}' "
                            f"({abs(under_val):.0f}% under-bias) to protect availability."
                        )

    # ------------------------------------------------------------------ #
    # 2) Demand variability (coefficient of variation)
    # ------------------------------------------------------------------ #
    var_c = _pick_segment(df, [sku_c, roles.get("category"), loc_c])
    date_c = roles.get("date")
    if var_c is not None and date_c is not None:
        tmp = df[[var_c, date_c]].copy()
        tmp["a"] = actual.values
        daily = tmp.groupby([var_c, date_c])["a"].sum().reset_index()
        cv = (
            daily.groupby(var_c)["a"]
            .agg(lambda s: (s.std(ddof=0) / s.mean()) if s.mean() else np.nan)
            .dropna()
        )
        if not cv.empty:
            volatile = cv[cv > 0.5]
            out["metrics"]["median_cv"] = float(cv.median())
            if not volatile.empty:
                worst = cv.idxmax()
                out["findings"].append(
                    f"{len(volatile)} of {len(cv)} {var_c}s are high-volatility "
                    f"(CV>0.5); worst is '{worst}' (CV {cv[worst]:.2f}) — needs "
                    "safety stock / scenario planning, not a flat forecast."
                )
                out["actions"].append(
                    f"Move the {len(volatile)} high-CV {var_c}s onto dynamic safety "
                    "stock and review them in the weekly S&OP, not monthly."
                )

    # ------------------------------------------------------------------ #
    # 3) Inventory risk: days-of-cover (stockout vs waste)
    # ------------------------------------------------------------------ #
    if inv_c is not None and date_c is not None:
        d = df[[date_c]].copy()
        d["inv"] = _num(df, inv_c).values
        d["a"] = actual.values
        d[date_c] = pd.to_datetime(d[date_c], errors="coerce", format="mixed")
        grp_cols = [c for c in [loc_c, sku_c] if c]
        for c in grp_cols:
            d[c] = df[c].values

        avg_daily = actual.sum() / max(df[date_c].nunique() if date_c in df else 1, 1) \
            if date_c in df.columns else actual.mean()
        latest = d[date_c].max()
        latest_inv = d[d[date_c] == latest]["inv"].sum()
        if avg_daily and avg_daily > 0:
            cover = latest_inv / avg_daily
            out["metrics"]["days_of_cover"] = float(cover)
            out["findings"].append(
                f"Network days-of-cover is {cover:.1f} days at current demand."
            )

        # per-location stockout / overstock flags
        if loc_c is not None and date_c in df.columns:
            n_days = df[date_c].nunique() if not pd.api.types.is_datetime64_any_dtype(df[date_c]) \
                else pd.to_datetime(df[date_c], errors="coerce").nunique()
            per = d.dropna(subset=[date_c])
            latest_inv_loc = per[per[date_c] == latest].groupby(loc_c)["inv"].sum()
            daily_loc = per.groupby(loc_c)["a"].sum() / max(n_days, 1)
            cover_loc = (latest_inv_loc / daily_loc.replace(0, np.nan)).dropna()
            if not cover_loc.empty:
                stockout = cover_loc[cover_loc < 2.0]
                overstock = cover_loc[cover_loc > 10.0]
                if not stockout.empty:
                    worst = stockout.idxmin()
                    out["findings"].append(
                        f"Stockout risk: {len(stockout)} store(s) under 2 days cover — "
                        f"worst '{worst}' at {stockout.min():.1f} days."
                    )
                    out["actions"].append(
                        f"Expedite replenishment to '{worst}' and the "
                        f"{len(stockout)-1} other thin store(s) before the weekend peak."
                    )
                if not overstock.empty:
                    worst_o = overstock.idxmax()
                    out["findings"].append(
                        f"Overstock/waste risk: {len(overstock)} store(s) above 10 days "
                        f"cover — worst '{worst_o}' at {overstock.max():.1f} days."
                    )

    # ------------------------------------------------------------------ #
    # 4) Promo uplift
    # ------------------------------------------------------------------ #
    if promo_c is not None:
        p = _num(df, promo_c).fillna(0)
        on = actual[p > 0]
        off = actual[p == 0]
        if len(on) > 5 and off.mean():
            uplift = (on.mean() - off.mean()) / off.mean() * 100.0
            out["metrics"]["promo_uplift_pct"] = float(uplift)
            out["findings"].append(
                f"Promotions lift average unit demand by {uplift:.0f}% — size promo "
                "forecasts and inventory to this, not to baseline."
            )
            if uplift > 30:
                out["actions"].append(
                    f"Pre-position inventory for promo SKUs at a ~{uplift:.0f}% uplift "
                    "and add promo flags to the forecast so peaks aren't treated as noise."
                )

    return out


def _pick_segment(df: pd.DataFrame, candidates: list[str | None]) -> str | None:
    for c in candidates:
        if c is not None and c in df.columns:
            return c
    return None
