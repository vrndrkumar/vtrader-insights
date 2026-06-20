"""
Orchestrator — VTrader Stock Analyser
Always runs fresh on every call. Never serves cached results.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import StockAnalysisReport, StockMstr, MarketOverview
from .. import market_data
from . import technical as technical_module
from . import llm_engine
from . import scoring

settings = get_settings()


# ─────────────────────────────────────────────────────────────────────
# JSON sanitizer — converts Python bools / numpy types for MySQL JSON
# ─────────────────────────────────────────────────────────────────────

def _json_safe(obj: Any) -> Any:
    import numpy as np
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return int(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [_json_safe(v) for v in obj.tolist()]
    if isinstance(obj, set):
        return list(obj)
    return obj


# ─────────────────────────────────────────────────────────────────────
# Plain-English reasons from pattern engine (used when LLM unavailable)
# ─────────────────────────────────────────────────────────────────────

def _build_swing_reasons(
    technical: dict,
    verdict: str,
    suggested_setup: dict,
) -> Tuple[List[str], List[str]]:
    """
    Returns (why_recommended, why_not_or_caveats) as plain-English lists.
    Reads from pattern engine output + indicator data.
    No raw numbers or formulas — just what was found and what it means.
    """
    why:     List[str] = []
    why_not: List[str] = []

    pat_data = technical.get("pattern_data", {})
    patterns = pat_data.get("patterns", [])
    detected = [p for p in patterns if p.get("detected")]

    # ── Positive: high-scoring patterns ──────────────────────────────
    for p in detected:
        name = p.get("name", "")
        desc = p.get("description", "")
        conf = p.get("confidence", "")
        pts  = p.get("score_contribution", 0)
        if pts >= 10:
            why.append(f"{name} ({conf} confidence) — {desc}")
        elif pts >= 5:
            why.append(f"{name} — {desc}")

    # ── Positive: indicator signals ───────────────────────────────────
    trend     = technical.get("trend", "")
    rsi       = technical.get("rsi14")
    pct_hi    = technical.get("pct_from_52w_high")
    vol_ratio = technical.get("volume_ratio_10d_vs_50d")
    structure = technical.get("structure", "")
    rr        = suggested_setup.get("risk_reward_ratio")

    if trend == "Uptrend":
        why.append("Price above both SMA50 and SMA200 — full trend alignment confirmed")
    elif "Early Recovery" in trend:
        why.append("Price has recovered above SMA200 — early stage trend recovery underway, SMA50 catching up")

    if rsi and 45 <= rsi <= 65:
        why.append(f"RSI at {rsi:.0f} — healthy momentum zone, not overbought")
    elif rsi and 30 <= rsi < 45:
        why.append(f"RSI at {rsi:.0f} — recovering from oversold, valid entry zone at bottoms")

    if pct_hi and -25 <= pct_hi <= -5:
        why.append(f"Stock is {abs(pct_hi):.0f}% below its 52-week high — meaningful room to run before hitting resistance")

    if vol_ratio and vol_ratio >= 1.2:
        why.append(f"Volume running {vol_ratio:.1f}x above average — smart money accumulation signal")

    if rr and rr >= 3.0:
        why.append(f"Risk:Reward of {rr}:1 — excellent setup, risking ₹1 to make ₹{rr}")
    elif rr and rr >= 2.0:
        why.append(f"Risk:Reward of {rr}:1 — meets minimum threshold for a quality swing trade")

    # ── Negative: flags and warnings ─────────────────────────────────
    if trend == "Downtrend":
        why_not.append("Stock is in a downtrend — price below both SMA50 and SMA200. High risk of further decline. Wait for trend reversal before entering.")

    if rsi and rsi > 72:
        why_not.append(f"RSI at {rsi:.0f} — overbought territory. Momentum buyers may be exhausted. Risky entry point right now.")

    if rsi and rsi < 25:
        why_not.append(f"RSI at {rsi:.0f} — very oversold with no recovery signal yet. Stock could fall further before bottoming.")

    if pct_hi and pct_hi > -3:
        why_not.append("Stock is trading near its 52-week high — limited upside before hitting major resistance. Not an ideal entry.")

    if pct_hi and pct_hi < -40:
        why_not.append(f"Stock is {abs(pct_hi):.0f}% below its 52-week high — this may indicate a structurally broken trend, not just a temporary dip.")

    if "Choppy" in structure or "No Clear" in structure:
        why_not.append("No clear directional structure detected — stock is moving sideways without conviction. Wait for a base to form before entering.")

    if "Extended" in structure:
        why_not.append("Stock has already broken out and is extended above support — late entry risk is high. Better to wait for a pullback to a proper base.")

    if rr and rr < 2.0:
        why_not.append(f"Risk:Reward is only {rr}:1 — below the 2:1 minimum. The potential reward does not justify the risk at current levels.")

    if vol_ratio and vol_ratio <= 0.6:
        why_not.append(f"Volume is only {vol_ratio:.1f}x average — very low participation suggests lack of institutional interest.")

    # ── Pattern narrative as closing summary ──────────────────────────
    narrative = pat_data.get("pattern_narrative", "")
    if narrative:
        if detected:
            why.append(f"Overall pattern assessment: {narrative}")
        else:
            why_not.append(f"Overall pattern assessment: {narrative}")

    # ── Fallback if absolutely nothing fired ──────────────────────────
    if not why and not why_not:
        score = technical.get("technical_score", 0)
        if score >= 60:
            why.append(f"Technical score of {score:.0f}/100 based on price structure and indicator alignment — moderate conviction")
        else:
            why_not.append(f"Technical score of {score:.0f}/100 — insufficient pattern or indicator confirmation. Not recommended at this stage.")

    return why, why_not


# ─────────────────────────────────────────────────────────────────────
# Market data fetcher
# ─────────────────────────────────────────────────────────────────────

def _get_quote_and_history(stock: StockMstr):
    provider = market_data.get_provider()
    quote = market_data.quote_from_latest_update(stock.latest_update)
    if quote is None:
        try:
            quote = provider.get_quote(stock.symbol_code, stock.exchange, stock.token_id)
        except Exception:
            quote = {
                "ltp": None, "prev_close": None, "open": None,
                "high": None, "low": None, "volume": None,
                "change_pct": None, "ts": datetime.utcnow().isoformat(),
                "source": "unavailable",
            }
    try:
        history = provider.get_history(
            stock.symbol_code, stock.exchange, stock.token_id, days=400
        )
    except Exception:
        import pandas as pd
        history = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    return quote, history


# ─────────────────────────────────────────────────────────────────────
# Main analysis pipeline
# ─────────────────────────────────────────────────────────────────────

def analyze_stock(db: Session, stock: StockMstr) -> StockAnalysisReport:
    """Always runs fresh — never returns a cached result."""

    # Step 1: fresh market data
    quote, history = _get_quote_and_history(stock)

    # Step 2: technical analysis + pattern engine
    technical       = technical_module.compute_technical(history, quote)
    suggested_setup = technical_module.suggest_trade_setup(technical)

    # Step 3: qualitative research (Claude — may be unavailable)
    llm_result = llm_engine.analyze_stock_with_llm(
        symbol_name     = stock.symbol_name,
        symbol_code     = stock.symbol_code or "",
        exchange        = stock.exchange or "",
        technical       = technical,
        suggested_setup = suggested_setup,
        sector          = getattr(stock, "sector",   None) or "",
        industry        = getattr(stock, "industry",  None) or "",
        description     = getattr(stock, "description", None) or "",
    )

    fundamental  = llm_result.get("fundamental", {})
    sector       = llm_result.get("sector", {})
    momentum     = llm_result.get("momentum", {})
    swing        = llm_result.get("swing_view", {})
    long_term    = llm_result.get("long_term_view", {})
    risk_factors_raw = llm_result.get("risk_factors", [])
    # Filter out generic fallback messages
    risk_factors = [
        r for r in risk_factors_raw
        if "Qualitative analysis unavailable" not in str(r)
        and "treat scores as technical" not in str(r)
    ]
    # If no real risks from LLM, build from technicals
    if not risk_factors:
        _rsi   = technical.get("rsi14")
        _trend = technical.get("trend", "")
        _pchi  = technical.get("pct_from_52w_high")
        _vr    = technical.get("volume_ratio_10d_vs_50d")
        _str   = technical.get("structure", "")
        if "Downtrend" in _trend:
            risk_factors.append("Stock is in a confirmed downtrend — price below SMA50 and SMA200. Risk of further decline.")
        if _rsi and _rsi > 72:
            risk_factors.append(f"RSI overbought at {_rsi:.0f} — momentum may reverse. Avoid chasing at current levels.")
        if _pchi and _pchi < -40:
            risk_factors.append(f"Stock is {abs(_pchi):.0f}% below 52-week high — potential structural damage, not just a dip.")
        if _vr and _vr < 0.5:
            risk_factors.append("Volume is significantly below average — low liquidity increases slippage risk on entry/exit.")
        if "Choppy" in _str or "Extended" in _str:
            risk_factors.append(f"Chart structure is '{_str}' — increased risk of false signals or whipsaws.")
        if not risk_factors:
            risk_factors.append("No Anthropic API key configured — fundamental and sector risks not assessed. Treat this as a technical-only signal.")

    # Step 4: scoring
    fundamental_score = float(fundamental.get("score", 50) or 50)
    technical_score   = float(technical.get("technical_score", 50) or 50)
    sector_score      = float(sector.get("sector_strength_score", 50) or 50)
    momentum_score    = float(momentum.get("momentum_score", 50) or 50)

    overall    = scoring.weighted_final_score(fundamental_score, technical_score, sector_score, momentum_score)
    red_flags  = scoring.has_fundamental_red_flags(fundamental)
    verdict    = scoring.verdict_for_score(overall, red_flags, suggested_setup.get("risk_reward_ratio"))
    confidence = scoring.confidence_for(overall, verdict)
    probability = scoring.probability_3_6m(overall, verdict)

    # Step 5: build why/why_not — use LLM result if available, else pattern engine
    llm_why     = swing.get("why_recommended", [])
    llm_why_not = swing.get("why_not_or_caveats", [])

    # Consider it "empty" if LLM returned nothing real
    # (generic fallback text is not useful — replace with pattern-based reasons)
    GENERIC_FALLBACK = "Qualitative research could not be generated"
    llm_why_real     = [r for r in llm_why     if GENERIC_FALLBACK not in str(r)]
    llm_why_not_real = [r for r in llm_why_not if GENERIC_FALLBACK not in str(r)]

    if not llm_why_real and not llm_why_not_real:
        llm_why, llm_why_not = _build_swing_reasons(technical, verdict, suggested_setup)
    else:
        llm_why, llm_why_not = llm_why_real, llm_why_not_real

    swing_view_payload = {
        "trade_setup":            suggested_setup,
        "why_recommended":        llm_why,
        "why_not_or_caveats":     llm_why_not,
        "technical_trend":        technical.get("trend"),
        "support_levels":         technical.get("support_levels", []),
        "resistance_levels":      technical.get("resistance_levels", []),
        "chart_structure":        swing.get("chart_structure") or technical.get("structure"),
        "trade_setup_commentary": swing.get("trade_setup_commentary"),
    }

    # Step 6: sanitize all JSON (bools, numpy types → JSON-safe)
    technical_safe    = _json_safe(technical)
    swing_view_safe   = _json_safe(swing_view_payload)
    fundamental_safe  = _json_safe(fundamental)
    sector_safe       = _json_safe(sector)
    momentum_safe     = _json_safe(momentum)
    long_term_safe    = _json_safe(long_term)
    risk_factors_safe = _json_safe(risk_factors)
    quote_safe        = _json_safe(quote)

    # Step 7: persist — mark old reports not-latest, insert fresh row
    db.query(StockAnalysisReport).filter(
        StockAnalysisReport.stock_id == stock.id,
        StockAnalysisReport.is_latest == True,  # noqa: E712
    ).update({"is_latest": False}, synchronize_session="fetch")
    db.flush()

    report = StockAnalysisReport(
        stock_id           = stock.id,
        symbol_code        = stock.symbol_code,
        exchange           = stock.exchange,
        sector             = getattr(stock, "sector",   None),
        industry           = getattr(stock, "industry", None),
        category           = getattr(stock, "category", None),
        overall_score      = overall,
        fundamental_score  = fundamental_score,
        technical_score    = technical_score,
        sector_score       = sector_score,
        momentum_score     = momentum_score,
        verdict            = verdict,
        confidence         = confidence,
        probability_3_6m   = probability,
        swing_view         = swing_view_safe,
        long_term_view     = long_term_safe,
        technical_detail   = technical_safe,
        fundamental_detail = fundamental_safe,
        sector_detail      = sector_safe,
        momentum_detail    = momentum_safe,
        risk_factors       = risk_factors_safe,
        raw_quote          = quote_safe,
        is_latest          = True,
        generated_at       = datetime.utcnow(),
    )
    db.add(report)
    db.commit()
    db.expire_all()
    db.refresh(report)
    return report


def get_latest_report(db: Session, stock_id: int) -> Optional[StockAnalysisReport]:
    db.expire_all()
    return (
        db.query(StockAnalysisReport)
        .filter(
            StockAnalysisReport.stock_id == stock_id,
            StockAnalysisReport.is_latest == True,  # noqa: E712
        )
        .order_by(StockAnalysisReport.generated_at.desc())
        .first()
    )


def report_is_fresh(report: Optional[StockAnalysisReport]) -> bool:
    if report is None or report.generated_at is None:
        return False
    return (datetime.utcnow() - report.generated_at) <= timedelta(
        minutes=settings.report_freshness_minutes
    )


def refresh_market_overview(db: Session) -> MarketOverview:
    raw = llm_engine.generate_market_overview()
    overview = MarketOverview(
        market_view       = raw.get("market_view"),
        favoured_sectors  = raw.get("favoured_sectors", []),
        avoid_sectors     = raw.get("avoid_sectors", []),
        key_risks         = raw.get("key_risks", []),
        key_opportunities = raw.get("key_opportunities", []),
        raw               = _json_safe(raw),
        generated_at      = datetime.utcnow(),
    )
    db.add(overview)
    db.commit()
    db.refresh(overview)
    return overview


def get_latest_market_overview(db: Session) -> Optional[MarketOverview]:
    return (
        db.query(MarketOverview)
        .order_by(MarketOverview.generated_at.desc())
        .first()
    )