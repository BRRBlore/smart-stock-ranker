# ============================================================
# app.py — Bapi's Smart Stock Ranker V2
# 5 tabs: Ranker | Value Zone | Sector Heat Map | Deep Dive | Momentum
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os

st.set_page_config(
    page_title="Bapi's Smart Stock Ranker",
    page_icon="📊", layout="wide",
    initial_sidebar_state="expanded",
)

from scoring import calculate_score
from config  import (APP_TITLE, CLOUD_CSV, PILLAR_WEIGHTS,
                     SECTOR_PE, GRADE_THRESHOLDS)

IS_CLOUD = not os.path.exists("data/smart_ranker.db")

# ── Local-only imports ────────────────────────────────────────────────────────
if not IS_CLOUD:
    try:
        from database import (init_db, get_all_stocks, get_scrape_progress,
                               acknowledge_alerts, get_alerts)
        from batch_scraper import start_batch_scrape, stop_scrape
        from auto_universe import update_universe
        from export_to_csv import export
        init_db()
        LOCAL_OK = True
    except Exception as e:
        LOCAL_OK = False
else:
    LOCAL_OK = False

# ── Column map: SQLite → display names ───────────────────────────────────────
COL_MAP = {
    "ticker":"Ticker","name":"Name","sector":"Sector","sector_pe":"Sector_PE",
    "price":"Price","price_1m_ret":"Price_1M_Ret","price_3m_ret":"Price_3M_Ret",
    "price_6m_ret":"Price_6M_Ret","low_52w":"Low_52W","high_52w":"High_52W",
    "pct_above_52w_low":"Pct_Above_52W_Low","price_trend":"Price_Trend",
    "volume_trend":"Volume_Trend","pe":"PE","pb":"PB","roe":"RoE","roce":"RoCE",
    "de":"DE","revenue_growth":"Revenue_Growth","market_cap_cr":"Market_Cap_Cr",
    "fii_pct":"FII_Pct","dii_pct":"DII_Pct","promoter_pct":"Promoter_Pct",
    "fii_selling_4q":"FII_Selling_4Q","dii_buying_4q":"DII_Buying_4Q",
    "fii_trend_pct":"FII_Trend_Pct","dii_trend_pct":"DII_Trend_Pct",
    "fii_label":"FII_Label","dii_label":"DII_Label",
    "composite_score":"Score","grade":"Grade","rank":"Rank",
    "score_value":"Score_Value","score_quality":"Score_Quality",
    "score_momentum":"Score_Momentum","score_smartmoney":"Score_SmartMoney",
    "rank_value":"Rank_Value","rank_quality":"Rank_Quality",
    "rank_momentum":"Rank_Momentum","rank_smartmoney":"Rank_SmartMoney",
    "fair_value":"Fair_Value","buy_zone_low":"Buy_Zone_Low",
    "buy_zone_high":"Buy_Zone_High","strong_buy_below":"Strong_Buy_Below",
    "value_signal":"Value_Signal","scrape_status":"Scrape_Status",
    "last_updated":"Last_Updated",
}

def _rename(df):
    df = df.copy()
    df.columns = [COL_MAP.get(c, c) for c in df.columns]
    return df

# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    # 1. SQLite (local)
    if LOCAL_OK:
        try:
            df = get_all_stocks()
            if not df.empty:
                df = _rename(df)
                if "Score" not in df.columns:
                    df = calculate_score(df)
                return df.sort_values("Score", ascending=False).reset_index(drop=True)
        except Exception:
            pass
    # 2. cloud_data.csv
    if os.path.exists(CLOUD_CSV):
        try:
            df = pd.read_csv(CLOUD_CSV)
            df = _rename(df)
            if "Score" not in df.columns:
                df = calculate_score(df)
            return df.sort_values("Score", ascending=False).reset_index(drop=True)
        except Exception:
            pass
    return pd.DataFrame()

# ── Load data BEFORE sidebar so filters can use it ───────────────────────────
df = load_data()
_all_names    = sorted(df["Name"].dropna().unique().tolist())    if not df.empty and "Name"   in df.columns else []
_all_sectors  = sorted(df["Sector"].dropna().unique().tolist())  if not df.empty and "Sector" in df.columns else []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Controls")
    if IS_CLOUD:
        st.info("☁️ Cloud mode — data auto-refreshes daily at 4am IST")
    st.divider()

    if LOCAL_OK:
        st.subheader("📡 Data Refresh")
        try:
            prog = get_scrape_progress()
            if prog.get("running") and prog.get("total", 0) > 0:
                pct = prog["completed"] / prog["total"]
                st.progress(pct, text=f"Scraping {prog['completed']}/{prog['total']}")
        except Exception:
            pass
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 New", use_container_width=True):
                st.toast(start_batch_scrape(force=False))
                st.cache_data.clear()
        with c2:
            if st.button("🔁 All", use_container_width=True):
                st.toast(start_batch_scrape(force=True))
                st.cache_data.clear()
    else:
        if st.button("🔄 Reload", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.subheader("🔍 Filters")

    min_score   = st.slider("Min Score", 0, 100, 30, step=5)
    min_mcap    = st.slider("Min Market Cap (₹ Cr)", 0, 10000, 500, step=500)
    sectors_sel = st.multiselect("Sectors", options=_all_sectors,
                                  default=_all_sectors, key="sectors")
    sig_filter  = st.multiselect("Value Signal",
                    ["STRONG BUY","BUY","WATCH","FAIR VALUE","OVERVALUED"])
    company_sel = st.multiselect("🔎 Search Company", options=_all_names,
                                  default=[], placeholder="Type to search...")

    st.divider()
    with st.expander("📐 Pillar Weights"):
        for p, w in PILLAR_WEIGHTS.items():
            st.caption(f"{p}: **{w}%**")

# ── Apply filters ─────────────────────────────────────────────────────────────
st.title(APP_TITLE)

if df.empty:
    if IS_CLOUD:
        st.warning("No data yet. The daily automation will populate this at 4am IST. "
                   "To load data now, run `python batch_scraper.py` locally and push `cloud_data.csv`.")
    else:
        st.warning("No data. Click **New** or **All** in sidebar to start scraping.")
    st.stop()

flt = df.copy()
if "Score"         in flt.columns: flt = flt[flt["Score"] >= min_score]
if "Market_Cap_Cr" in flt.columns: flt = flt[flt["Market_Cap_Cr"] >= min_mcap]
if sectors_sel and "Sector" in flt.columns:
    flt = flt[flt["Sector"].isin(sectors_sel)]
if sig_filter and "Value_Signal" in flt.columns:
    flt = flt[flt["Value_Signal"].str.contains("|".join(sig_filter), na=False)]
if company_sel and "Name" in flt.columns:
    flt = flt[flt["Name"].isin(company_sel)]

# ── Summary metrics ───────────────────────────────────────────────────────────
total_stocks = len(flt)
avg_score    = flt["Score"].mean() if "Score" in flt.columns else 0
buy_count    = flt["Value_Signal"].str.contains("BUY", na=False).sum() if "Value_Signal" in flt.columns else 0
top10_pct    = len(flt[flt["Score"] >= flt["Score"].quantile(0.9)]) if len(flt) > 10 else 0

c1,c2,c3,c4 = st.columns(4)
c1.metric("Stocks",        str(total_stocks))
c2.metric("Avg Score",     f"{avg_score:.1f}/100")
c3.metric("In Value Zone", str(buy_count))
c4.metric("Top 10% (≥A)", str(top10_pct))

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
t1, t2, t3, t4, t5 = st.tabs([
    "🏅 Overall Ranker",
    "💰 Value Zones",
    "🌡️ Sector Heat Map",
    "🔬 Deep Dive",
    "🚀 Momentum Screen",
])


# ══════ TAB 1 — OVERALL RANKER ═══════════════════════════════════════════════
with t1:
    st.subheader("Multi-Factor Stock Ranker")
    st.caption("Ranked by composite score across all 4 pillars: Value · Quality · Momentum · Smart Money")

    # Top 50 bar chart sorted by rank
    top_n = flt.head(50) if len(flt) > 50 else flt
    signal_colors_map = {
        "STRONG BUY": "#1B5E20", "BUY": "#388E3C",
        "WATCH": "#F9A825", "FAIR VALUE": "#1565C0",
    }
    def _bar_color(sig):
        s = str(sig).upper()
        if "STRONG BUY" in s: return "#1B5E20"
        if "BUY"        in s: return "#388E3C"
        if "WATCH"      in s: return "#F9A825"
        if "FAIR VALUE" in s: return "#1565C0"
        return "#C62828"

    if not top_n.empty and "Score" in top_n.columns:
        chart_df = top_n.sort_values("Score", ascending=True)
        colors   = [_bar_color(v) for v in chart_df.get("Value_Signal", pd.Series())]
        labels   = [f"#{r} {g}" for r, g in zip(
                    chart_df.get("Rank", range(len(chart_df))),
                    chart_df.get("Grade", [""] * len(chart_df)))]
        fig = go.Figure(go.Bar(
            x=chart_df["Score"], y=chart_df["Name"],
            orientation="h", marker_color=colors,
            text=labels, textposition="outside", textfont=dict(size=9),
        ))
        fig.add_vline(x=60, line_dash="dash", line_color="#1565C0",
                      annotation_text="A grade threshold")
        fig.update_layout(
            xaxis=dict(title="Composite Score (0–100)", range=[0, 120]),
            yaxis=dict(title="", categoryorder="array",
                       categoryarray=chart_df["Name"].tolist()),
            height=max(400, len(chart_df) * 28),
            margin=dict(l=150, r=100, t=30, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Full table with pillar breakdown
    show_cols = [c for c in [
        "Rank","Name","Sector","Price","Score","Grade",
        "Score_Value","Score_Quality","Score_Momentum","Score_SmartMoney",
        "Value_Signal","Market_Cap_Cr","PE","PB","RoE",
    ] if c in flt.columns]

    def _sig_color(val):
        s = str(val)
        if "STRONG BUY" in s: return "background-color:#E8F5E9;color:#1B5E20;font-weight:bold"
        if "BUY"        in s: return "background-color:#F1F8E9;color:#2E7D32"
        if "WATCH"      in s: return "background-color:#FFF9C4;color:#7F4F00"
        if "OVERVALUED" in s: return "background-color:#FFEBEE;color:#B71C1C"
        return ""

    fmt_map = {
        "Price":"₹{:.0f}","Score":"{:.1f}","Score_Value":"{:.1f}",
        "Score_Quality":"{:.1f}","Score_Momentum":"{:.1f}",
        "Score_SmartMoney":"{:.1f}","PE":"{:.1f}x","PB":"{:.1f}x",
        "RoE":"{:.1f}%","Market_Cap_Cr":"₹{:,.0f}Cr",
    }
    fmt = {k: v for k, v in fmt_map.items() if k in show_cols}
    ren = {"Score":"Score","Value_Signal":"Signal","Market_Cap_Cr":"MCap ₹Cr",
           "Score_Value":"Value","Score_Quality":"Quality",
           "Score_Momentum":"Momentum","Score_SmartMoney":"SmartMoney"}
    try:
        styled = (flt[show_cols].rename(columns=ren)
            .style
            .map(_sig_color, subset=["Signal"] if "Signal" in
                 [ren.get(c,c) for c in show_cols] else [])
            .format({ren.get(k,k):v for k,v in fmt.items()})
            .background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=100))
        st.dataframe(styled, use_container_width=True, height=450)
    except Exception:
        st.dataframe(flt[show_cols], use_container_width=True, height=450)


# ══════ TAB 2 — VALUE ZONES ══════════════════════════════════════════════════
with t2:
    st.subheader("Price vs Fair Value — Value Buy Zones")
    st.caption("Green band = 10–20% discount to fair value. Dark green = 30%+ discount (strong buy).")

    if "Value_Signal" in flt.columns:
        vdf = flt[flt["Value_Signal"].str.contains("BUY|STRONG", na=False, regex=True)]

        if not vdf.empty:
            chart_vdf = vdf.head(40).sort_values("Score", ascending=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=chart_vdf["Name"],
                x=chart_vdf.get("Buy_Zone_High",0) - chart_vdf.get("Buy_Zone_Low",0),
                base=chart_vdf.get("Buy_Zone_Low",0),
                orientation="h", name="Buy Zone",
                marker_color="rgba(56,142,60,0.5)",
            ))
            fig.add_trace(go.Scatter(
                y=chart_vdf["Name"], x=chart_vdf.get("Fair_Value",0),
                mode="markers", name="Fair Value",
                marker=dict(symbol="line-ns",size=12,color="#1565C0",
                            line=dict(width=2,color="#1565C0")),
            ))
            price_colors = [_bar_color(v) for v in chart_vdf.get("Value_Signal", pd.Series())]
            fig.add_trace(go.Scatter(
                y=chart_vdf["Name"], x=chart_vdf.get("Price",0),
                mode="markers", name="Current Price",
                marker=dict(size=9, color=price_colors),
            ))
            fig.update_layout(
                barmode="overlay",
                xaxis_title="Price (₹)",
                height=max(400, len(chart_vdf)*34),
                margin=dict(l=160, r=60, t=30, b=40),
                yaxis=dict(categoryorder="array",
                           categoryarray=chart_vdf["Name"].tolist()),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Expandable cards for each value stock
        st.subheader(f"Stocks in Value Zone ({len(vdf)})")
        for _, row in vdf.head(30).iterrows():
            fv = float(row.get("Fair_Value",0) or 0)
            pr = float(row.get("Price",0) or 0)
            disc = (fv-pr)/fv*100 if fv>0 else 0
            sig  = str(row.get("Value_Signal",""))
            icon = "🟢🟢" if "STRONG" in sig else "🟢"
            with st.expander(
                f"{icon} **{row.get('Name','')}** [{row.get('Sector','')}] — "
                f"₹{pr:.0f}  ({disc:+.1f}% vs fair value ₹{fv:.0f})  "
                f"Score: {row.get('Score',0):.0f}"
            ):
                a,b,c,d,e = st.columns(5)
                a.metric("Price",      f"₹{pr:.0f}")
                b.metric("Fair Value", f"₹{fv:.0f}")
                c.metric("Buy Zone",   f"₹{float(row.get('Buy_Zone_Low',0) or 0):.0f}–₹{float(row.get('Buy_Zone_High',0) or 0):.0f}")
                d.metric("Score",      f"{float(row.get('Score',0)):.0f}/100")
                e.metric("Grade",      str(row.get("Grade","—")))


# ══════ TAB 3 — SECTOR HEAT MAP ══════════════════════════════════════════════
with t3:
    st.subheader("Sector Heat Map")
    st.caption("Average composite score by sector — darker = higher ranked sector overall")

    if "Sector" in flt.columns and "Score" in flt.columns:
        sector_stats = (flt.groupby("Sector")
            .agg(
                Avg_Score=("Score","mean"),
                Count=("Score","count"),
                Avg_PE=("PE","mean"),
                Avg_RoE=("RoE","mean"),
                Buy_Count=("Value_Signal", lambda x: x.str.contains("BUY",na=False).sum()),
            )
            .reset_index()
            .sort_values("Avg_Score", ascending=False)
        )
        sector_stats["Avg_Score"] = sector_stats["Avg_Score"].round(1)
        sector_stats["Avg_PE"]    = sector_stats["Avg_PE"].round(1)
        sector_stats["Avg_RoE"]   = sector_stats["Avg_RoE"].round(1)
        sector_stats["Buy_%"]     = (sector_stats["Buy_Count"] / sector_stats["Count"] * 100).round(0)

        # Heat map bar chart
        fig = px.bar(
            sector_stats.sort_values("Avg_Score"),
            x="Avg_Score", y="Sector", orientation="h",
            color="Avg_Score", color_continuous_scale="RdYlGn",
            range_color=[20, 70],
            text="Avg_Score",
            labels={"Avg_Score": "Avg Score"},
            title="Average Composite Score by Sector",
        )
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        fig.update_layout(
            height=max(400, len(sector_stats)*28),
            margin=dict(l=150, r=60, t=50, b=40),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Sector table
        st.subheader("Sector Summary Table")
        try:
            styled_sec = (sector_stats
                .rename(columns={"Avg_Score":"Avg Score","Count":"# Stocks",
                                 "Avg_PE":"Avg PE","Avg_RoE":"Avg RoE%",
                                 "Buy_Count":"# In Value Zone","Buy_%":"% In Value"})
                .style
                .background_gradient(subset=["Avg Score"], cmap="RdYlGn", vmin=20, vmax=70)
                .format({"Avg Score":"{:.1f}","Avg PE":"{:.1f}x",
                         "Avg RoE%":"{:.1f}%","% In Value":"{:.0f}%"}))
            st.dataframe(styled_sec, use_container_width=True)
        except Exception:
            st.dataframe(sector_stats, use_container_width=True)

        # Scatter: Avg Score vs # Stocks
        fig2 = px.scatter(
            sector_stats, x="Count", y="Avg_Score",
            size="Buy_Count", color="Avg_Score",
            color_continuous_scale="RdYlGn", range_color=[20,70],
            text="Sector", hover_data=["Buy_%"],
            labels={"Count":"# Stocks","Avg_Score":"Avg Score","Buy_Count":"# In Value Zone"},
            title="Sectors — Stock Count vs Avg Score (bubble = # in value zone)",
        )
        fig2.update_traces(textposition="top center", textfont=dict(size=9))
        fig2.update_layout(height=480, coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)


# ══════ TAB 4 — DEEP DIVE ════════════════════════════════════════════════════
with t4:
    st.subheader("Individual Stock Deep Dive")
    names = flt["Name"].tolist() if "Name" in flt.columns else []
    if not names:
        st.info("No stocks to display.")
    else:
        sel = st.selectbox("Select stock", options=names)
        row = flt[flt["Name"] == sel].iloc[0]

        # Header metrics
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("Price",     f"₹{float(row.get('Price',0) or 0):.0f}",
                  delta=f"{float(row.get('Price_3M_Ret',0) or 0):+.1f}% 3M")
        c2.metric("Rank",      f"#{int(row.get('Rank',0) or 0)}")
        c3.metric("Score",     f"{float(row.get('Score',0) or 0):.1f}/100")
        c4.metric("Grade",     str(row.get("Grade","—")))
        c5.metric("Signal",    str(row.get("Value_Signal","—")))
        c6.metric("MCap",      f"₹{float(row.get('Market_Cap_Cr',0) or 0):,.0f}Cr")

        st.divider()

        # 4-Pillar radar
        left, right = st.columns(2)
        with left:
            pillar_scores = {
                "Value":      float(row.get("Score_Value",0) or 0),
                "Quality":    float(row.get("Score_Quality",0) or 0),
                "Momentum":   float(row.get("Score_Momentum",0) or 0),
                "SmartMoney": float(row.get("Score_SmartMoney",0) or 0),
            }
            labels  = list(pillar_scores.keys()) + [list(pillar_scores.keys())[0]]
            vals    = list(pillar_scores.values()) + [list(pillar_scores.values())[0]]
            fig_radar = go.Figure(go.Scatterpolar(
                r=vals, theta=labels, fill="toself",
                fillcolor="rgba(33,150,243,0.2)",
                line=dict(color="#1565C0", width=2),
                marker=dict(size=6),
            ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                showlegend=False,
                title=f"4-Pillar Breakdown — {sel}",
                height=340, margin=dict(t=60,b=20,l=40,r=40),
            )
            st.plotly_chart(fig_radar, use_container_width=True)

            # Pillar rank table
            st.markdown("#### Pillar Rankings")
            total = len(df)
            pillar_data = {
                "Pillar":  ["Value","Quality","Momentum","Smart Money"],
                "Score":   [f"{pillar_scores['Value']:.1f}",
                            f"{pillar_scores['Quality']:.1f}",
                            f"{pillar_scores['Momentum']:.1f}",
                            f"{pillar_scores['SmartMoney']:.1f}"],
                "Rank":    [f"#{int(row.get('Rank_Value',0) or 0)} / {total}",
                            f"#{int(row.get('Rank_Quality',0) or 0)} / {total}",
                            f"#{int(row.get('Rank_Momentum',0) or 0)} / {total}",
                            f"#{int(row.get('Rank_SmartMoney',0) or 0)} / {total}"],
                "Weight":  ["25%","30%","20%","25%"],
            }
            st.dataframe(pd.DataFrame(pillar_data), use_container_width=True, hide_index=True)

        with right:
            st.markdown("#### Fundamentals")
            for k,v in {
                "P/E":          f"{float(row.get('PE',0) or 0):.1f}x  (sector: {float(row.get('Sector_PE',22) or 22):.1f}x)",
                "P/B":          f"{float(row.get('PB',0) or 0):.2f}x",
                "RoE":          f"{float(row.get('RoE',0) or 0):.1f}%",
                "RoCE":         f"{float(row.get('RoCE',0) or 0):.1f}%",
                "D/E":          f"{float(row.get('DE',0) or 0):.2f}x",
                "Revenue Gr.":  f"{float(row.get('Revenue_Growth',0) or 0):.1f}%",
                "Mkt Cap":      f"₹{float(row.get('Market_Cap_Cr',0) or 0):,.0f} Cr",
            }.items():
                a,b = st.columns([2,3]); a.caption(k); b.write(v)

            st.markdown("#### Price Performance")
            for k,v in {
                "1M Return":  f"{float(row.get('Price_1M_Ret',0) or 0):+.1f}%",
                "3M Return":  f"{float(row.get('Price_3M_Ret',0) or 0):+.1f}%",
                "6M Return":  f"{float(row.get('Price_6M_Ret',0) or 0):+.1f}%",
                "52W Range":  f"₹{float(row.get('Low_52W',0) or 0):.0f} – ₹{float(row.get('High_52W',0) or 0):.0f}",
                "Trend":      str(row.get("Price_Trend","—")),
                "Volume":     str(row.get("Volume_Trend","—")),
            }.items():
                a,b = st.columns([2,3]); a.caption(k); b.write(v)

            st.markdown("#### Smart Money")
            for k,v in {
                "FII %":     f"{float(row.get('FII_Pct',0) or 0):.1f}% → {row.get('FII_Label','')}",
                "DII %":     f"{float(row.get('DII_Pct',0) or 0):.1f}% → {row.get('DII_Label','')}",
                "Promoter":  f"{float(row.get('Promoter_Pct',0) or 0):.1f}%",
            }.items():
                a,b = st.columns([2,3]); a.caption(k); b.write(v)

        # Valuation zone
        st.divider()
        st.markdown("#### Value Zone")
        a,b,c,d = st.columns(4)
        a.metric("Current",    f"₹{float(row.get('Price',0) or 0):.0f}")
        b.metric("Fair Value", f"₹{float(row.get('Fair_Value',0) or 0):.0f}")
        c.metric("Buy Zone",
                 f"₹{float(row.get('Buy_Zone_Low',0) or 0):.0f}–₹{float(row.get('Buy_Zone_High',0) or 0):.0f}")
        d.metric("Strong Buy", f"₹{float(row.get('Strong_Buy_Below',0) or 0):.0f}")


# ══════ TAB 5 — MOMENTUM SCREEN ══════════════════════════════════════════════
with t5:
    st.subheader("🚀 Momentum Screener")
    st.caption(
        "Stocks with strong price momentum + good fundamentals = potential breakout candidates. "
        "Different from value investing — these are already moving."
    )

    if "Score_Momentum" in flt.columns and "Score_Quality" in flt.columns:
        # Filter: high momentum AND reasonable quality
        mom_df = flt[
            (flt["Score_Momentum"] >= 60) &
            (flt["Score_Quality"]  >= 50)
        ].copy()

        if mom_df.empty:
            st.info("No stocks match momentum + quality criteria with current filters. Try reducing Min Score.")
        else:
            # Scatter: 3M return vs Quality score
            fig_scatter = px.scatter(
                mom_df,
                x="Score_Quality",
                y="Score_Momentum",
                size="Score",
                color="Sector",
                hover_name="Name",
                hover_data={
                    "Price_3M_Ret": ":.1f",
                    "Score": ":.1f",
                    "Value_Signal": True,
                },
                labels={
                    "Score_Quality":  "Quality Score (0–100)",
                    "Score_Momentum": "Momentum Score (0–100)",
                },
                title=f"Quality vs Momentum — {len(mom_df)} stocks",
                height=500,
            )
            fig_scatter.add_hline(y=70, line_dash="dot", line_color="grey",
                                   annotation_text="High momentum")
            fig_scatter.add_vline(x=65, line_dash="dot", line_color="grey",
                                   annotation_text="High quality")
            st.plotly_chart(fig_scatter, use_container_width=True)

            st.caption(
                "🔵 Top-right quadrant = High Quality + High Momentum = strongest candidates"
            )

            # Table
            mom_show = [c for c in [
                "Rank","Name","Sector","Price","Score","Score_Momentum",
                "Score_Quality","Price_3M_Ret","Price_6M_Ret",
                "Volume_Trend","Value_Signal","RoE","DE",
            ] if c in mom_df.columns]
            ren2 = {
                "Score":"Overall","Score_Momentum":"Momentum",
                "Score_Quality":"Quality","Price_3M_Ret":"3M Ret%",
                "Price_6M_Ret":"6M Ret%","Volume_Trend":"Volume",
                "Value_Signal":"Signal",
            }
            fmt2 = {
                "Price":"₹{:.0f}","Overall":"{:.1f}","Momentum":"{:.1f}",
                "Quality":"{:.1f}","3M Ret%":"{:+.1f}%","6M Ret%":"{:+.1f}%",
                "RoE":"{:.1f}%","DE":"{:.2f}x",
            }
            try:
                styled_mom = (mom_df[mom_show]
                    .sort_values("Score_Momentum", ascending=False)
                    .rename(columns=ren2)
                    .style
                    .map(_sig_color, subset=["Signal"] if "Signal" in
                         [ren2.get(c,c) for c in mom_show] else [])
                    .format({ren2.get(k,k):v for k,v in fmt2.items()})
                    .background_gradient(subset=["Momentum"], cmap="Blues", vmin=0, vmax=100))
                st.dataframe(styled_mom, use_container_width=True, height=400)
            except Exception:
                st.dataframe(mom_df[mom_show], use_container_width=True, height=400)

    else:
        st.info("Score data not available. Run batch_scraper.py to generate scores.")
