"""
LLM research engine.

This is what makes the system "real time": for every stock (or for the
overall market), we ask Claude -- with its hosted web_search tool turned
on -- to research current fundamentals, sector positioning and recent
news, and return a structured JSON object that slots directly into the
report schema.

If ANTHROPIC_API_KEY is not configured (e.g. local dev), every function
here degrades gracefully to a clearly-labelled placeholder so the rest
of the pipeline (technical scoring, dashboard, UI) keeps working.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from anthropic import Anthropic

from ..config import get_settings

settings = get_settings()

_client: Optional[Anthropic] = None


def _get_client() -> Optional[Anthropic]:
    global _client
    if not settings.anthropic_api_key:
        return None
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _extract_json(text: str) -> Dict[str, Any]:
    """Claude is instructed to return raw JSON, but strip code fences just in case."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    # If there's leading/trailing prose, grab the outermost {...}
    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
    return json.loads(cleaned)


def _call_claude(system: str, user: str) -> str:
    client = _get_client()
    if client is None:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    tools = []
    if settings.claude_enable_web_search:
        tools.append({
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": settings.claude_max_search_uses,
        })

    resp = client.messages.create(
        model=settings.claude_model,
        max_tokens=settings.claude_max_tokens,
        system=system,
        tools=tools or None,
        messages=[{"role": "user", "content": user}],
    )

    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts)


# ---------------------------------------------------------------------
# Per-stock research
# ---------------------------------------------------------------------
STOCK_SYSTEM_PROMPT = """You are a senior Indian equity research analyst and swing-trading \
strategist. You will be given a stock's identity plus pre-computed technical metrics. \
Use web search to find CURRENT information: latest quarterly results, business \
developments, sector news, analyst views, and 52-week price context.

Respond with ONLY a single JSON object (no markdown fences, no commentary) matching \
EXACTLY this schema:

{
  "fundamental": {
    "rating": "Strong|Good|Average|Weak",
    "score": 0-100,
    "business_quality_notes": "2-3 sentences",
    "financial_health_notes": "2-3 sentences",
    "ownership_notes": "1-2 sentences on promoter/institutional holding trends if known, else 'Not available'",
    "valuation_notes": "1-2 sentences comparing valuation to peers/history",
    "red_flags": ["short bullet", "..."]
  },
  "sector": {
    "sector_name": "string",
    "sector_trend": "Bullish|Neutral|Bearish",
    "sector_strength_score": 0-100,
    "sector_outlook": "2-3 sentences on the next 3-6 months",
    "growth_drivers": ["...", "..."],
    "risks": ["...", "..."]
  },
  "momentum": {
    "momentum_score": 0-100,
    "relative_strength_assessment": "1-2 sentences vs Nifty and sector peers",
    "accumulation_distribution": "1-2 sentences - is the stock under accumulation or distribution?"
  },
  "swing_view": {
    "why_recommended": ["reason 1", "reason 2", "reason 3"],
    "why_not_or_caveats": ["caveat 1", "caveat 2"],
    "chart_structure": "one of: Base Building, Near Breakout, Already Extended, Pullback Within Uptrend, Downtrend, Choppy",
    "trade_setup_commentary": "1-2 sentences validating or adjusting the pre-computed entry/stop/targets given fundamentals/news"
  },
  "long_term_view": {
    "thesis": "2-4 sentences on the 1-3 year structural story",
    "structural_score": 0-100,
    "growth_drivers": ["...", "..."],
    "long_term_risks": ["...", "..."],
    "valuation_view": "1-2 sentences - is current valuation reasonable for a 1-3yr holder?",
    "suitable_for_long_term": true/false
  },
  "risk_factors": ["top-level risk 1", "top-level risk 2", "top-level risk 3"]
}

Be objective and specific to THIS company -- avoid generic boilerplate. If you cannot \
find recent information, say so explicitly in the relevant notes field rather than \
guessing. Scores should reflect genuine differentiation between strong and weak \
companies, not cluster around 50-60 for everything."""


def analyze_stock_with_llm(
    symbol_name: str,
    symbol_code: str,
    exchange: str,
    technical: Dict[str, Any],
    suggested_setup: Dict[str, Any],
    sector: str = "",
    industry: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """Returns the parsed JSON described in STOCK_SYSTEM_PROMPT, or a fallback dict."""

    # Build enrichment context from DB if available
    enrichment_lines = []
    if sector:      enrichment_lines.append(f"Sector: {sector}")
    if industry:    enrichment_lines.append(f"Industry: {industry}")
    if description: enrichment_lines.append(f"Company description: {description}")
    enrichment_ctx = ("\n".join(enrichment_lines) + "\n") if enrichment_lines else ""

    user_prompt = f"""Company: {symbol_name} ({exchange}:{symbol_code})
{enrichment_ctx}

Pre-computed technical snapshot (from price history, you do not need to recompute this):
- Current price: {technical.get('current_price')}
- 52-week range: {technical.get('week52_low')} - {technical.get('week52_high')}
- % from 52w high: {technical.get('pct_from_52w_high')}%
- % from 52w low: {technical.get('pct_from_52w_low')}%
- Trend: {technical.get('trend')}
- Structure (preliminary): {technical.get('structure')}
- RSI(14): {technical.get('rsi14')}
- SMA20/50/200: {technical.get('sma20')}/{technical.get('sma50')}/{technical.get('sma200')}
- Support levels: {technical.get('support_levels')}
- Resistance levels: {technical.get('resistance_levels')}
- Technical score (preliminary, 0-100): {technical.get('technical_score')}

Pre-computed price-action trade setup (you may validate/adjust in trade_setup_commentary,
but DO NOT change the numeric levels yourself -- just comment on whether they make sense
given fundamentals/news):
- Entry zone: {suggested_setup.get('entry_zone_low')} - {suggested_setup.get('entry_zone_high')}
- Breakout trigger: {suggested_setup.get('breakout_trigger')}
- Stop loss: {suggested_setup.get('stop_loss')}
- Targets: {suggested_setup.get('target1')} / {suggested_setup.get('target2')} / {suggested_setup.get('target3')}

Research this company's current fundamentals, sector, and recent news, then return the
JSON object as specified."""

    try:
        raw = _call_claude(STOCK_SYSTEM_PROMPT, user_prompt)
        return _extract_json(raw)
    except Exception as exc:  # noqa: BLE001
        return _fallback_stock_result(str(exc))


def _fallback_stock_result(error: str) -> Dict[str, Any]:
    return {
        "fundamental": {
            "rating": "Average",
            "score": 50,
            "business_quality_notes": f"LLM research unavailable ({error}). Configure ANTHROPIC_API_KEY to enable.",
            "financial_health_notes": "Not available.",
            "ownership_notes": "Not available.",
            "valuation_notes": "Not available.",
            "red_flags": [],
        },
        "sector": {
            "sector_name": "Unclassified",
            "sector_trend": "Neutral",
            "sector_strength_score": 50,
            "sector_outlook": "LLM research unavailable.",
            "growth_drivers": [],
            "risks": [],
        },
        "momentum": {
            "momentum_score": 50,
            "relative_strength_assessment": "Not available.",
            "accumulation_distribution": "Not available.",
        },
        "swing_view": {
            "why_recommended": [],
            "why_not_or_caveats": [],
            "chart_structure": "Choppy",
            "trade_setup_commentary": "Levels are price-action only (no fundamental validation).",
        },
        "long_term_view": {
            "thesis": "LLM research unavailable.",
            "structural_score": 50,
            "growth_drivers": [],
            "long_term_risks": [],
            "valuation_view": "Not available.",
            "suitable_for_long_term": None,
        },
        "risk_factors": ["Qualitative analysis unavailable -- treat scores as technical-only."],
    }


# ---------------------------------------------------------------------
# Market-wide overview
# ---------------------------------------------------------------------
MARKET_SYSTEM_PROMPT = """You are a senior Indian equity strategist. Use web search to \
research the CURRENT state of Indian equity markets (Nifty/Sensex level and trend, FII/DII \
flows, sector calls from major brokerages) and respond with ONLY this JSON object:

{
  "market_view": "3-5 sentence overall market view for the next 3-6 months",
  "favoured_sectors": [{"sector": "name", "rationale": "1 sentence"}],
  "avoid_sectors": [{"sector": "name", "rationale": "1 sentence"}],
  "key_risks": ["risk 1", "risk 2", "risk 3"],
  "key_opportunities": ["opportunity 1", "opportunity 2", "opportunity 3"]
}"""


def generate_market_overview() -> Dict[str, Any]:
    try:
        raw = _call_claude(MARKET_SYSTEM_PROMPT, "Generate the current Indian market overview JSON.")
        return _extract_json(raw)
    except Exception as exc:  # noqa: BLE001
        return {
            "market_view": f"LLM research unavailable ({exc}). Configure ANTHROPIC_API_KEY to enable live market overviews.",
            "favoured_sectors": [],
            "avoid_sectors": [],
            "key_risks": [],
            "key_opportunities": [],
        }