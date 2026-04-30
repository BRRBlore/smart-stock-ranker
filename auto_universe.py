#!/usr/bin/env python3
# ============================================================
# auto_universe.py — NSE Official Data Edition
# ============================================================
# NSE publishes EQUITY_L.csv daily at:
# https://archives.nseindia.com/content/equities/EQUITY_L.csv
#
# This file is FREE, requires NO login, and contains ALL
# actively listed NSE equities with their symbols + company names.
# We filter by market cap using yfinance to find mid/small caps.
# ============================================================

import time
import requests
import pandas as pd
from io import StringIO
from pathlib import Path
from datetime import datetime

from database import init_db, upsert_universe, get_universe

NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
MIN_MCAP_CR = 500
MAX_MCAP_CR = 9_999_999

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/csv,*/*",
    "Referer": "https://www.nseindia.com/",
}

NAME_SECTOR = [
    (["bank"],                                                  "Banking"),
    (["financ","capital","wealth","prudent","sbfc","arman",
      "satin","repco","homefirst","aavas","aptus","ugro",
      "muthoot","manappuram","edelweiss","geojit","angelone",
      "creditacc","spandana","equitas","ujjivan","utkarsh",
      "esaf","jana","sammaan","finopb","paisalo","indostar"],   "Finance"),
    (["pharma","medic","drug","lifesci","biotech","bioscien",
      "natco","ajanta","caplin","supriya","rubicon","blissgvs",
      "orchid","novartis","windlas","lincoln","senores","akums",
      "emcure","ipca","granules","strides","alembic","marksans",
      "neuland","syncom","cohance","solara","suven","wock"],    "Pharmaceuticals"),
    (["health","hospital","diagnost","pathlabs","thyro","vimta",
      "narayana","aster","krsnaa","metropolis","medplus",
      "suraksha","yatharth","artemis","nephro","ventive"],      "Healthcare"),
    (["software","tech","infosy","digit","infosec","system",
      "solution","netweb","sonata","newgen","ceinsys","cigniti",
      "expleo","rsystem","ivalue","dynacons","hexaware","kpit",
      "tanla","intellect","mastek","coforge","datamatics",
      "sasken","latentview","nazara","rategain","route",
      "capillary","fractal","affle","moschip","zensar",
      "birlasoft","mphasis","happiest","cyient"],               "IT"),
    (["auto","motor","wagon","axle","tyre","gabriel","carraro",
      "sharda","pricol","sml","forcemot","swaraj","varroc",
      "minda","jtekt","subros","jamna","lumax","talbros","rane",
      "sansera","craftsman","endurance","escorts","apollotyre",
      "ceat","jktyre","balkrisind","belrise"],                  "Automobiles"),
    (["chemical","chemi","agrochem","fineotex","epigral","ghcl",
      "styrenix","kingfa","bayer","dhanuka","krishnaph","privi",
      "tatva","navinfluor","hikal","vinati","aether","rossari",
      "camlin","vidhi","neogen","fluorochem","gujalkali",
      "thirumalai","nocil","anupam"],                          "Chemicals"),
    (["solar","power","energy","electric","renew","turbine",
      "insolation","kpgreen","saatvikg","vikramsolar","emmvee",
      "websol","danishpower","gkenergy","orianapower","solex",
      "solarworld","waareeener","kpigreen","inoxgreen","inoxwind",
      "jppower","sjvn","ptcind","gipcl"],                      "Power"),
    (["cement","jklakshmi","starcement","heidelberg","manglmcem",
      "orientcem","prismjohn","ramcocem","nuvoco","birlacorpn",
      "sanghi","sagcem","dalmia","acc"],                        "Cement"),
    (["steel","metal","copper","alumin","iron","alloys",
      "maithanall","jaibalaji","ratnamani","gpil","himadri",
      "gravita","steelcas","sanduma","gallantt","kalyanisteels",
      "ushamart","sunflag","heg","graphite","electrosteel",
      "nmdc","midhani","moil","kiocl"],                        "Metals"),
    (["fmcg","consumer","hygiene","food","beverag","jyothylab",
      "emamiltd","bajajcon","heritgfood","dodla","gokulagro",
      "piccadily","vadilal","avantifeed","bikaji","gopal",
      "prataap","tastybite","hatsun","adffoods","ltfoods",
      "balramchin","banarisug","renuka","bajajhind"],           "FMCG"),
    (["realty","housing","infracon","construct","infra","build",
      "maninfra","ashoka","bondada","knrcon","nbcc","gptinfra",
      "dilip","jkumar","hginfra","pncinfra","pateleng","ceigall",
      "ahlucont","capacite","koltepatil","ajmera","mahlife",
      "sobha","purva","keystonerealty","sunteck","brigade",
      "marathon","tarc","signature","omaxe","ashiana"],         "Real Estate"),
    (["hotel","travel","eih","benares","tajgvk","orienthotel",
      "chalethotels","samhi","lemontree","mhril","leela",
      "juniper","thomascook","easemytrip","ixigo","itdc"],      "Hotels"),
    (["pump","engg","engineer","equip","machin","elgiequip",
      "ajaxengg","tdpowersys","rajooeng","kilbchenin","elecon",
      "concordenv","jash","thejo","vikranengg","macpower",
      "voltamp","disa","isgec","ksb","bharatbijlee","thermax",
      "honaut","kennamet","kec","kalpataru","technoel",
      "prajind","esab"],                                       "Engineering"),
    (["defence","defense","aero","grse","zentec","bhansalieng",
      "kernex","krishnadef","unimech","hblpower","avantel",
      "cochinship","mtartech","paras","apollomicro","ideaforge",
      "midhani","rosselltech","centum","datapattns"],           "Defence"),
    (["media","music","studio","tipsfilms","dbcorp","niitltd",
      "suntv","zeel","jagran","saregama","balajitele","hathway",
      "primefocus"],                                           "Media"),
    (["telecom","tatacomm","stltech","hfcl","tejasnet","nelco",
      "dlink"],                                                "Telecom"),
    (["logist","transport","cargo","railtel","rites","irctc",
      "transrail","gppl","knowledgem","vrllog","tciexpress",
      "bluedart","concor","allcargo","westcarrind","mahlog",
      "tvssupply","updaterser","kapston","redington"],          "Logistics"),
    (["gold","jewel","diamond","gems","skygold","shantigold",
      "dpabhushan","shringar","goldiam","thangamayl","sencogold",
      "kalyankjil","pngjl","motisons","bluestone","laxmigold"],  "Jewellery"),
    (["textile","garment","stylam","manyavar","pageind","redtape",
      "studds","arvind","vardhman","trident","raymond","icil",
      "siyaram","dollar","luxind","rupa","montecarlo",
      "kewalind","spal","gocolors","cantabil"],                 "Textiles"),
]

def _infer_sector(name: str) -> str:
    n = name.lower().replace(" ", "").replace(".", "").replace("&", "")
    for keywords, sector in NAME_SECTOR:
        if any(k.replace(" ","").replace(".","") in n for k in keywords):
            return sector
    return "Miscellaneous"


def fetch_nse_equity_list() -> pd.DataFrame:
    """Download EQUITY_L.csv from NSE archives — free, no login."""
    print("Downloading NSE EQUITY_L.csv...")
    try:
        resp = requests.get(NSE_EQUITY_URL, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")
        df = pd.read_csv(StringIO(resp.text))
        df.columns = [c.strip() for c in df.columns]
        print(f"  Total NSE securities: {len(df)}")
        return df
    except Exception as e:
        print(f"  [ERROR] Cannot fetch NSE equity list: {e}")
        return pd.DataFrame()


def get_market_caps_batch(symbols: list[str],
                           batch_size: int = 50) -> dict[str, float]:
    """
    Fetch market caps for symbols using yfinance batch download.
    Returns {symbol: market_cap_in_crores}
    """
    import yfinance as yf

    caps = {}
    tickers = [s + ".NS" for s in symbols]
    print(f"  Fetching market caps ({len(tickers)} stocks in batches of {batch_size})...")

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        try:
            data = yf.Tickers(" ".join(batch))
            for tk in batch:
                sym = tk.replace(".NS", "")
                try:
                    mc = data.tickers[tk].fast_info.market_cap or 0
                    caps[sym] = round(mc / 1e7, 2)  # INR → Crores
                except Exception:
                    caps[sym] = 0.0
        except Exception as e:
            print(f"    Batch {i//batch_size + 1} error: {e}")
            for tk in batch:
                caps[tk.replace(".NS", "")] = 0.0

        if i % (batch_size * 5) == 0 and i > 0:
            print(f"    Processed {i}/{len(tickers)}...")
        time.sleep(0.5)

    return caps


def update_universe(min_mcap: float = MIN_MCAP_CR,
                    max_mcap: float = MAX_MCAP_CR) -> int:
    """
    Core function called by GitHub Actions.
    1. Downloads NSE EQUITY_L.csv
    2. Finds symbols not yet in our universe
    3. Fetches market caps for new symbols
    4. Adds those in range to universe table
    """
    print(f"\n{'='*50}")
    print(f"NSE Universe Auto-Discovery")
    print(f"Target: ₹{min_mcap:,.0f} – {max_mcap:,.0f} Cr")
    print(f"{'='*50}\n")

    # Get NSE list
    nse_df = fetch_nse_equity_list()
    if nse_df.empty:
        print("Skipping — NSE list unavailable.")
        return 0

    # Filter EQ series only (regular equity, not warrants/DVR/rights etc)
    if "SERIES" in nse_df.columns:
        nse_df = nse_df[nse_df["SERIES"].str.strip() == "EQ"].copy()
    print(f"  After EQ filter: {len(nse_df)} regular equities\n")

    # Identify column names (NSE file format can vary slightly)
    sym_col  = next((c for c in nse_df.columns if "symbol" in c.lower()), nse_df.columns[0])
    name_col = next((c for c in nse_df.columns if "name" in c.lower()), nse_df.columns[1])

    all_symbols = nse_df[sym_col].str.strip().str.upper().tolist()

    # Find what's NOT already in our universe
    existing = get_universe()
    existing_syms = set()
    if not existing.empty:
        existing_syms = {
            t.replace(".NS","").replace(".BO","").upper()
            for t in existing["ticker"].tolist()
        }
    print(f"  Current universe: {len(existing_syms)} stocks")

    new_syms = [s for s in all_symbols if s not in existing_syms]
    print(f"  New symbols on NSE: {len(new_syms)}")

    if not new_syms:
        print("  Universe fully up to date — nothing to add.")
        return 0

    # Cap at 500 per run to avoid very long GitHub Actions jobs
    if len(new_syms) > 500:
        print(f"  Capping at 500 for this run (remaining will be picked up next run)")
        new_syms = new_syms[:500]

    # Fetch market caps
    caps = get_market_caps_batch(new_syms, batch_size=50)

    # Filter by market cap and build rows
    now = datetime.now().isoformat()
    rows = []

    for sym in new_syms:
        mc = caps.get(sym, 0.0)
        if mc < min_mcap or mc > max_mcap:
            continue

        # Get company name from NSE list
        mask  = nse_df[sym_col].str.strip().str.upper() == sym
        match = nse_df[mask]
        name  = match[name_col].iloc[0].strip() if not match.empty else sym

        rows.append({
            "ticker":        sym + ".NS",
            "name":          name,
            "sector":        _infer_sector(name),
            "screener_id":   sym,
            "market_cap_cr": mc,
            "pe":  0.0, "pb": 0.0, "roe": 0.0,
            "added_on": now,
        })

    print(f"\n  In mcap range: {len(rows)} new stocks to add")

    if rows:
        upsert_universe(rows)
        for r in rows[:20]:
            print(f"    ✓ {r['name']:<40} {r['ticker']:<16} ₹{r['market_cap_cr']:>10,.0f} Cr")
        if len(rows) > 20:
            print(f"    ... and {len(rows)-20} more")

    return len(rows)


if __name__ == "__main__":
    init_db()
    added = update_universe()
    print(f"\nDone. {added} new stocks added to universe.")
