# ============================================================
# scoring.py — 4-Pillar Multi-Factor Ranking Engine
# ============================================================
# Pillars: Value (25%) | Quality (30%) | Momentum (20%) | Smart Money (25%)
# Each factor scored 0–10, weighted to produce 0–100 composite
# ============================================================

import pandas as pd
import numpy as np
from config import SECTOR_PE, FACTOR_WEIGHTS, GRADE_THRESHOLDS


# ── Factor scoring functions (each returns 0–10) ──────────────────────────────

def _score_pe_discount(pe: float, sector_pe: float) -> float:
    """Score PE discount vs sector average. Lower PE = higher score."""
    if pe <= 0 or sector_pe <= 0:
        return 5.0  # neutral if no data
    discount = (sector_pe - pe) / sector_pe * 100
    if discount >= 40:  return 10.0
    if discount >= 25:  return 8.0
    if discount >= 10:  return 6.0
    if discount >= 0:   return 4.0
    if discount >= -20: return 2.0
    return 0.0


def _score_pb(pb: float) -> float:
    """Score Price/Book ratio. Lower is better for value investors."""
    if pb <= 0: return 5.0
    if pb <= 0.8:  return 10.0
    if pb <= 1.2:  return 9.0
    if pb <= 1.8:  return 7.0
    if pb <= 2.5:  return 5.0
    if pb <= 4.0:  return 3.0
    if pb <= 7.0:  return 1.5
    return 0.0


def _score_margin_of_safety(pct_above_low: float) -> float:
    """Score based on how close price is to 52W low."""
    if pct_above_low <= 0: return 5.0
    if pct_above_low <= 10:  return 10.0
    if pct_above_low <= 20:  return 8.0
    if pct_above_low <= 35:  return 6.0
    if pct_above_low <= 55:  return 3.5
    if pct_above_low <= 80:  return 1.5
    return 0.0


def _score_roe(roe: float) -> float:
    """Score Return on Equity."""
    if roe <= 0: return 0.0
    if roe >= 30: return 10.0
    if roe >= 22: return 8.5
    if roe >= 16: return 6.5
    if roe >= 12: return 4.5
    if roe >= 8:  return 2.5
    return 1.0


def _score_roce(roce: float) -> float:
    """Score Return on Capital Employed."""
    if roce <= 0: return 0.0
    if roce >= 30: return 10.0
    if roce >= 22: return 8.5
    if roce >= 15: return 6.5
    if roce >= 10: return 4.0
    if roce >= 5:  return 2.0
    return 0.5


def _score_revenue_growth(growth: float) -> float:
    """Score revenue growth YoY."""
    if growth >= 25:  return 10.0
    if growth >= 15:  return 8.0
    if growth >= 8:   return 6.0
    if growth >= 0:   return 3.5
    if growth >= -10: return 1.5
    return 0.0


def _score_debt(de: float) -> float:
    """Score Debt/Equity ratio. Lower = safer."""
    if de <= 0:   return 10.0   # debt-free
    if de <= 0.3: return 8.5
    if de <= 0.6: return 6.5
    if de <= 1.0: return 4.5
    if de <= 1.8: return 2.5
    if de <= 3.0: return 1.0
    return 0.0


def _score_price_return(ret_pct: float, benchmark_ret: float = 0.0) -> float:
    """
    Score price return vs benchmark (relative momentum).
    Excess return = stock return - benchmark return.
    """
    excess = ret_pct - benchmark_ret
    if excess >= 20:  return 10.0
    if excess >= 10:  return 8.0
    if excess >= 3:   return 6.5
    if excess >= -3:  return 5.0
    if excess >= -10: return 3.0
    if excess >= -20: return 1.5
    return 0.0


def _score_volume_trend(price_3m_ret: float, volume_trend: str) -> float:
    """
    Score volume trend. Rising volume with positive price = bullish.
    We use price_3m_ret as a proxy since volume trend is a string flag.
    """
    vt = str(volume_trend).lower()
    is_rising = "rising" in vt
    is_positive_price = price_3m_ret > 0

    if is_rising and is_positive_price:   return 10.0  # volume + price rising
    if is_rising and not is_positive_price: return 5.0  # high volume, falling price
    if not is_rising and is_positive_price: return 6.5  # price rising, normal volume
    return 3.0  # both flat/falling


def _score_fii_signal(fii_selling_4q: bool, fii_trend_pct: float,
                       dii_buying_4q: bool) -> float:
    """
    Contrarian FII signal. Selling + DII absorbing = strong buy signal.
    """
    if pd.isna(fii_trend_pct): fii_trend_pct = 0
    if fii_selling_4q and dii_buying_4q:  return 10.0  # perfect contrarian setup
    if fii_selling_4q and not dii_buying_4q: return 7.0  # FII selling only
    if not fii_selling_4q and fii_trend_pct > 2: return 4.0  # FII buying (crowded)
    return 5.0  # neutral


def _score_dii_signal(dii_buying_4q: bool, dii_trend_pct: float) -> float:
    """DII accumulation signal."""
    if pd.isna(dii_trend_pct): dii_trend_pct = 0
    if dii_buying_4q and dii_trend_pct >= 3: return 10.0
    if dii_buying_4q:                         return 7.5
    if dii_trend_pct > 0:                     return 5.0
    if dii_trend_pct < -2:                    return 2.0
    return 4.0


def _score_promoter(promoter_pct: float) -> float:
    """Score promoter holding. Higher = more skin in the game."""
    if pd.isna(promoter_pct) or promoter_pct <= 0: return 5.0
    if promoter_pct >= 65: return 10.0
    if promoter_pct >= 50: return 8.0
    if promoter_pct >= 35: return 6.0
    if promoter_pct >= 20: return 4.0
    return 2.0


# ── Main scoring function ─────────────────────────────────────────────────────

def calculate_score(df: pd.DataFrame,
                    benchmark_3m: float = 0.0,
                    benchmark_6m: float = 0.0) -> pd.DataFrame:
    """
    Score all stocks in the DataFrame.

    Args:
        df: DataFrame with raw stock data
        benchmark_3m: Nifty 500 3M return % (for relative momentum)
        benchmark_6m: Nifty 500 6M return % (for relative momentum)

    Returns:
        DataFrame with added score columns
    """
    df = df.copy()

    def g(col, default=0.0):
        """Safe column getter with default."""
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(default)
        return pd.Series([default] * len(df), index=df.index)

    def gb(col):
        """Safe boolean getter."""
        if col in df.columns:
            return df[col].fillna(False).astype(bool)
        return pd.Series([False] * len(df), index=df.index)

    def gs(col, default=""):
        """Safe string getter."""
        if col in df.columns:
            return df[col].fillna(default).astype(str)
        return pd.Series([default] * len(df), index=df.index)

    # ── Compute individual factor scores ──────────────────────────────────────
    pe         = g("pe")
    sector_pe  = g("sector_pe", 22.0)
    pb         = g("pb")
    pct_low    = g("pct_above_52w_low")
    roe        = g("roe")
    roce       = g("roce")
    rev_growth = g("revenue_growth")
    de         = g("de")
    ret_3m     = g("price_3m_ret")
    ret_6m     = g("price_6m_ret")
    vol_trend  = gs("volume_trend")
    fii_sell   = gb("fii_selling_4q")
    fii_pct    = g("fii_trend_pct")
    dii_buy    = gb("dii_buying_4q")
    dii_pct    = g("dii_trend_pct")
    promoter   = g("promoter_pct")

    # VALUE factors
    df["f_pe_discount"] = [
        _score_pe_discount(pe[i], sector_pe[i]) for i in range(len(df))
    ]
    df["f_pb"]              = pb.apply(_score_pb)
    df["f_margin_of_safety"]= pct_low.apply(_score_margin_of_safety)

    # QUALITY factors
    df["f_roe"]             = roe.apply(_score_roe)
    df["f_roce"]            = roce.apply(_score_roce)
    df["f_revenue_growth"]  = rev_growth.apply(_score_revenue_growth)
    df["f_debt_safety"]     = de.apply(_score_debt)

    # MOMENTUM factors
    df["f_price_3m"] = [
        _score_price_return(ret_3m[i], benchmark_3m) for i in range(len(df))
    ]
    df["f_price_6m"] = [
        _score_price_return(ret_6m[i], benchmark_6m) for i in range(len(df))
    ]
    df["f_volume_trend"] = [
        _score_volume_trend(ret_3m[i], vol_trend[i]) for i in range(len(df))
    ]

    # SMART MONEY factors
    df["f_fii_signal"] = [
        _score_fii_signal(fii_sell[i], fii_pct[i], dii_buy[i])
        for i in range(len(df))
    ]
    df["f_dii_signal"] = [
        _score_dii_signal(dii_buy[i], dii_pct[i]) for i in range(len(df))
    ]
    df["f_promoter"] = [
        _score_promoter(promoter[i]) for i in range(len(df))
    ]

    # ── Pillar scores (weighted sum of factor scores) ─────────────────────────
    w = FACTOR_WEIGHTS

    df["pillar_value"] = (
        df["f_pe_discount"]      * w["pe_discount"] +
        df["f_pb"]               * w["pb_ratio"] +
        df["f_margin_of_safety"] * w["margin_of_safety"]
    ) / w["pe_discount"] + w["pb_ratio"] + w["margin_of_safety"] * 10

    # Normalise each pillar to 0-100
    def _pillar(score_cols: list[str], weights: list[float]) -> pd.Series:
        total_weight = sum(weights)
        weighted = sum(df[c] * w for c, w in zip(score_cols, weights))
        return (weighted / total_weight).round(2)

    df["score_value"] = _pillar(
        ["f_pe_discount", "f_pb", "f_margin_of_safety"],
        [w["pe_discount"], w["pb_ratio"], w["margin_of_safety"]]
    ) * 10   # factor scores are 0-10, pillar score is 0-100

    df["score_quality"] = _pillar(
        ["f_roe", "f_roce", "f_revenue_growth", "f_debt_safety"],
        [w["roe"], w["roce"], w["revenue_growth"], w["debt_safety"]]
    ) * 10

    df["score_momentum"] = _pillar(
        ["f_price_3m", "f_price_6m", "f_volume_trend"],
        [w["price_3m"], w["price_6m"], w["volume_trend"]]
    ) * 10

    df["score_smartmoney"] = _pillar(
        ["f_fii_signal", "f_dii_signal", "f_promoter"],
        [w["fii_signal"], w["dii_signal"], w["promoter_holding"]]
    ) * 10

    # ── Composite score (0-100) ───────────────────────────────────────────────
    from config import PILLAR_WEIGHTS
    pw = PILLAR_WEIGHTS
    total_pw = sum(pw.values())

    df["composite_score"] = (
        df["score_value"]      * pw["Value"] +
        df["score_quality"]    * pw["Quality"] +
        df["score_momentum"]   * pw["Momentum"] +
        df["score_smartmoney"] * pw["SmartMoney"]
    ) / total_pw

    df["composite_score"] = df["composite_score"].clip(0, 100).round(1)

    # ── Overall rank ──────────────────────────────────────────────────────────
    df["rank"] = df["composite_score"].rank(ascending=False, method="min").astype(int)

    # Pillar ranks
    df["rank_value"]      = df["score_value"].rank(ascending=False, method="min").astype(int)
    df["rank_quality"]    = df["score_quality"].rank(ascending=False, method="min").astype(int)
    df["rank_momentum"]   = df["score_momentum"].rank(ascending=False, method="min").astype(int)
    df["rank_smartmoney"] = df["score_smartmoney"].rank(ascending=False, method="min").astype(int)

    # ── Grade ─────────────────────────────────────────────────────────────────
    def _grade(score: float) -> str:
        if score >= GRADE_THRESHOLDS["A+"]: return "A+"
        if score >= GRADE_THRESHOLDS["A"]:  return "A"
        if score >= GRADE_THRESHOLDS["B"]:  return "B"
        if score >= GRADE_THRESHOLDS["C"]:  return "C"
        return "D"

    df["grade"] = df["composite_score"].apply(_grade)

    # ── Valuation signal (same logic as V1) ───────────────────────────────────
    df = _add_valuation_signal(df)

    # Drop intermediate factor columns (keep scores and ranks clean)
    factor_cols = [c for c in df.columns if c.startswith("f_")]
    df.drop(columns=factor_cols, inplace=True, errors="ignore")

    return df.sort_values("composite_score", ascending=False).reset_index(drop=True)


def _add_valuation_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Add fair value and buy zone signals (same methodology as V1)."""
    from config import SECTOR_PE as SPE

    def _compute_row(row):
        price     = float(row.get("price", 0) or 0)
        pe        = float(row.get("pe", 0) or 0)
        pb        = float(row.get("pb", 0) or 0)
        sector    = str(row.get("sector", "Miscellaneous"))
        sector_pe = SPE.get(sector, 22.0)
        low_52w   = float(row.get("low_52w", 0) or price * 0.75)

        estimates = []
        if pe > 0 and price > 0:
            fair = (price / pe) * sector_pe
            if fair > 0: estimates.append(fair)
        if pb > 0 and price > 0:
            fair = (price / pb) * min(2.5, sector_pe / 10)
            if fair > 0: estimates.append(fair)
        if low_52w > 0:
            estimates.append(low_52w * 1.15)

        if not estimates:
            return pd.Series({
                "fair_value": 0, "buy_zone_high": 0, "buy_zone_low": 0,
                "strong_buy_below": 0, "value_signal": "No Data"
            })

        fv = sorted(estimates)[len(estimates) // 2]
        if   price <= 0:        sig = "No Data"
        elif price <= fv * 0.70: sig = "STRONG BUY"
        elif price <= fv * 0.80: sig = "BUY"
        elif price <= fv * 0.90: sig = "WATCH"
        elif price <= fv:        sig = "FAIR VALUE"
        else:
            sig = f"OVERVALUED +{round((price - fv) / fv * 100, 1)}%"

        return pd.Series({
            "fair_value":       round(fv, 2),
            "buy_zone_high":    round(fv * 0.90, 2),
            "buy_zone_low":     round(fv * 0.80, 2),
            "strong_buy_below": round(fv * 0.70, 2),
            "value_signal":     sig,
        })

    valuation = df.apply(_compute_row, axis=1)
    for col in valuation.columns:
        df[col] = valuation[col]

    return df
