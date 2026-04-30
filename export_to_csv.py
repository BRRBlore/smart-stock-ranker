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

    # Pull all scored stocks
    df = pd.read_sql(
        "SELECT * FROM stocks WHERE scrape_status='done' ORDER BY composite_score DESC",
        conn
    )
    conn.close()

    if df.empty:
        print("[WARNING] No scored stocks found in database.")
        return False

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
