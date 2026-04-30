# ============================================================
# config.py — Bapi's Smart Stock Ranker V2
# ============================================================

APP_TITLE = "📊 Bapi's Smart Stock Ranker"
APP_VERSION = "2.0"

# ── Universe ──────────────────────────────────────────────────────────────────
MIN_MCAP_CR   = 500       # ₹500 Cr minimum market cap
MAX_MCAP_CR   = 9_999_999 # No upper limit (covers large caps too)

# ── Data paths ────────────────────────────────────────────────────────────────
DATA_DIR      = "data"
DB_PATH       = "data/smart_ranker.db"
CLOUD_CSV     = "data/cloud_data.csv"
CACHE_HOURS   = 24

# ── Scraping ──────────────────────────────────────────────────────────────────
SCRAPE_DELAY_MIN = 2.0
SCRAPE_DELAY_MAX = 4.0
SCRAPE_RETRIES   = 3

SCREENER_BASE_URL = "https://www.screener.in/company/{screener_id}/consolidated/"
SCREENER_HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.screener.in/",
}

# ── Sector PE benchmarks ──────────────────────────────────────────────────────
SECTOR_PE = {
    "Banking":          12.0,
    "Finance":          18.0,
    "IT":               28.0,
    "Pharmaceuticals":  28.0,
    "Healthcare":       35.0,
    "FMCG":             45.0,
    "Automobiles":      20.0,
    "Auto Ancillaries": 22.0,
    "Chemicals":        25.0,
    "Power":            18.0,
    "Cement":           25.0,
    "Metals":           12.0,
    "Real Estate":      30.0,
    "Consumer Durables":35.0,
    "Engineering":      28.0,
    "Defence":          40.0,
    "Logistics":        22.0,
    "Media":            20.0,
    "Telecom":          20.0,
    "Hotels":           35.0,
    "Retail":           40.0,
    "Textiles":         18.0,
    "Agri":             20.0,
    "Jewellery":        30.0,
    "Packaging":        22.0,
    "Cables & Wires":   25.0,
    "Pipes & Tubes":    22.0,
    "Tyres & Rubber":   20.0,
    "Casting & Forging":20.0,
    "Mining":           12.0,
    "Miscellaneous":    22.0,
}

# ── 4-Pillar Scoring Weights ──────────────────────────────────────────────────
# Total = 100%

PILLAR_WEIGHTS = {
    "Value":       25,   # PE discount, PB, margin of safety
    "Quality":     30,   # RoE, RoCE, revenue growth, debt safety
    "Momentum":    20,   # price returns vs benchmark, volume trend
    "SmartMoney":  25,   # FII/DII trends, promoter holding
}

# Factor weights within each pillar (must sum to pillar weight)
FACTOR_WEIGHTS = {
    # VALUE (25%)
    "pe_discount":       10,   # PE vs sector average
    "pb_ratio":           8,   # Price to book value
    "margin_of_safety":   7,   # Price proximity to 52W low

    # QUALITY (30%)
    "roe":                8,   # Return on equity
    "roce":               8,   # Return on capital employed
    "revenue_growth":     7,   # Revenue growth YoY
    "debt_safety":        7,   # Low debt/equity

    # MOMENTUM (20%)
    "price_3m":           8,   # 3-month return vs Nifty 500
    "price_6m":           7,   # 6-month return
    "volume_trend":       5,   # 20D volume vs 60D average

    # SMART MONEY (25%)
    "fii_signal":        10,   # FII 4Q trend (selling = contrarian buy)
    "dii_signal":         8,   # DII 4Q accumulation
    "promoter_holding":   7,   # Promoter skin in the game
}

# ── Grade thresholds ──────────────────────────────────────────────────────────
GRADE_THRESHOLDS = {
    "A+": 75,
    "A":  60,
    "B":  45,
    "C":  30,
    "D":   0,
}

# ── V1 compatibility (used by data_pipeline.py) ───────────────────────────────
WATCHLIST         = {}   # empty — V2 uses universe table, not a fixed watchlist
DATA_CSV          = "data/smart_ranker_data.csv"
CACHE_CSV         = "data/smart_ranker_cache.csv"
REFRESH_HOURS     = 24
SCRAPE_DELAY_SECONDS = 2.5
