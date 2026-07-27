"""
Optional LLM narrative layer.

If an OPENAI_API_KEY is available, we ask an LLM to write the brief from the
VERIFIED FACTS produced by brief_engine.analyze(). Otherwise callers fall back
to the deterministic brief. Either way the numbers come from the code, so the
model cannot hallucinate figures.
"""
from __future__ import annotations

import json
import os
from typing import Any

SYSTEM_PROMPT = """You are a senior Demand Planning / S&OP lead writing the weekly demand
brief for supply, commercial and logistics leaders (up to VP level) at a
quick-commerce (dark store) business.
You are given a JSON object of VERIFIED FACTS already computed from the data
(forecast accuracy/bias, demand variability, days-of-cover, promo uplift, trends).
Rules:
- Use ONLY the numbers in FACTS. Never invent figures. If something is unknown, omit it.
- Be specific and quantified. Prefer "Snacks under-forecast 15%, driving stockouts"
  over "forecasts could improve". Frame everything around demand, forecast accuracy,
  availability vs waste, and the S&OP decision it triggers.
- Write for decisions, not description. Every takeaway implies a "so what" and an owner.
Output EXACTLY this structure in Markdown:

**TL;DR:** <one sentence, <=25 words>

**Three Key Takeaways**
1. <takeaway with number + implication>
2. <takeaway with number + implication>
3. <takeaway with number + implication>

**Recommended Action:** <one concrete, owner-ready next step tied to a takeaway>

**Risk Flags:** <comma-separated stockout / waste / forecast-bias risks, if any>"""


def _facts_for_prompt(facts: dict[str, Any]) -> dict[str, Any]:
    """Trim to the decision-relevant facts (keeps the prompt cheap + focused)."""
    keys = [
        "metric_col", "date_col", "dimension_col", "period",
        "metric_total", "metric_mean", "pop_change_pct", "overall_change_pct",
        "top_segment", "bottom_segment", "anomaly", "correlation", "findings",
        "is_demand", "demand", "demand_roles",
    ]
    return {k: facts[k] for k in keys if k in facts}


def llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def generate_brief_llm(facts: dict[str, Any], model: str = "gpt-4o-mini") -> str | None:
    """Return a markdown brief from the LLM, or None if unavailable/failed."""
    if not llm_available():
        return None
    try:
        from openai import OpenAI  # imported lazily so it's an optional dep

        client = OpenAI()
        facts_json = json.dumps(_facts_for_prompt(facts), indent=2)
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"FACTS:\n{facts_json}\n\nWrite the executive decision brief now."},
            ],
        )
        return resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001 - degrade gracefully to fallback
        print(f"[llm] falling back to deterministic brief: {exc}")
        return None
