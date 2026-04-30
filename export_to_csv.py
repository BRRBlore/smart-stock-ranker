#!/usr/bin/env python3
# ============================================================
# export_to_csv.py
# Exports SQLite scored stocks → data/cloud_data.csv
# Called locally and by GitHub Actions after batch scrape
# ============================================================

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

DB_PATH  = Path("data/smart_ranker.db")
CSV_PATH = Path("data/cloud_data.csv")


def export():
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found: {DB_PATH}")
        print("Run batch_scraper.py first to populate the database.")
        return False

    conn = sqlite3.connect(str(DB_PATH))

    # Pull all scraped stocks
    df = pd.read_sql(
        "SELECT * FROM stocks WHERE scrape_status='done'",
        conn
    )
    conn.close()

    if df.empty:
        print("[WARNING] No scraped stocks found in database.")
        return False

    # Score ALL stocks together in one pass — this is the correct approach.
    # Scoring one stock at a time (in batch_scraper) produces wrong results
    # because ranks and relative factors are meaningless on a single row.
    print(f"Scoring {len(df)} stocks in bulk...")
    from scoring import calculate_score
    df = calculate_score(df)
    df = df.sort_values("composite_score", ascending=False).reset_index(drop=True)
    print(f"Scoring complete. Score range: {df['composite_score'].min():.1f} – {df['composite_score'].max():.1f}")

    # Add metadata
    df["exported_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)

    print(f"\n[Done] Exported {len(df)} stocks → {CSV_PATH}")
    print(f"File size: {CSV_PATH.stat().st_size / 1024:.1f} KB")

    # Summary
    if "value_signal" in df.columns:
        print("\nSignal breakdown:")
        print(df["value_signal"].value_counts().to_string())
    if "smart_money_score" in df.columns:
        print(f"\nScore range: {df['smart_money_score'].min():.0f} – {df['smart_money_score'].max():.0f}")
        print(f"Avg score: {df['smart_money_score'].mean():.1f}")

    return True


if __name__ == "__main__":
    export()
