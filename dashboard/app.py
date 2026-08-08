"""
Mobile Money Fraud Analytics Dashboard
========================================

Self-contained Streamlit app: reads the raw synthetic data directly and
reimplements the fraud detection rules in pandas, so it can be demoed
locally with zero warehouse setup (`streamlit run app.py`).

The dbt_project/ directory contains the "real" warehouse-native version of
this same logic in SQL — this app is the fast, portable demo layer that
sits on top for portfolio walkthroughs.

Run:
    pip install streamlit plotly pandas
    streamlit run dashboard/app.py
"""

import gzip
import os

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

st.set_page_config(
    page_title="Mobile Money Fraud Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _inject_responsive_ui():
    """Inject a responsive meta tag and CSS tweaks for phones/tablets/desktop.

    Streamlit's layout is responsive by default, but these rules improve
    spacing, column stacking, and chart/table sizing across breakpoints.
    Both the current `data-testid` attributes and the legacy `.stXxx`
    class names are targeted, since Streamlit's internal class hashes
    (`.css-xxxxx`) are not stable across versions.
    """
    st.markdown(
        """
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
        <style>
        /* ---------- Base (desktop-first) ---------- */
        .block-container {padding:1.5rem 2rem 3rem; max-width:100%;}

        /* Charts and tables always fill their column and scroll horizontally
           rather than overflowing the viewport / getting clipped. */
        [data-testid="stDataFrame"], .stDataFrame,
        [data-testid="stPlotlyChart"], .stPlotlyChart,
        [data-testid="stElementContainer"], .element-container {
            width:100% !important;
            max-width:100% !important;
            overflow-x:auto;
            -webkit-overflow-scrolling:touch;
        }

        /* Tab strip scrolls horizontally instead of wrapping awkwardly */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            overflow-x:auto;
            flex-wrap:nowrap;
            -webkit-overflow-scrolling:touch;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {white-space:nowrap;}

        /* ---------- Tablet ---------- */
        @media (max-width: 900px) {
            .block-container {padding:1rem 1rem 2rem;}

            /* Let 4-up KPI rows wrap to 2x2 instead of squeezing to fit */
            [data-testid="stHorizontalBlock"] {flex-wrap:wrap !important;}
            [data-testid="stHorizontalBlock"] > [data-testid="column"],
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                min-width:45% !important;
                flex:1 1 45% !important;
            }
        }

        /* ---------- Phone ---------- */
        @media (max-width: 640px) {
            .block-container {padding:0.5rem 0.6rem 1.5rem;}

            h1 {font-size:1.4rem !important;}
            h2, [data-testid="stSubheader"] {font-size:1.1rem !important;}
            .stCaption, [data-testid="stCaptionContainer"] {font-size:0.8rem !important;}

            /* Stack every column group fully vertically on phones */
            [data-testid="stHorizontalBlock"] {flex-direction:column !important;}
            [data-testid="stHorizontalBlock"] > [data-testid="column"],
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                width:100% !important;
                min-width:100% !important;
                flex:1 1 100% !important;
            }

            /* Compact, stacked KPI metrics */
            [data-testid="stMetric"] {
                background:rgba(127,127,127,0.08);
                border-radius:0.5rem;
                padding:0.5rem 0.75rem;
                flex-direction:column !important;
                align-items:flex-start !important;
            }
            [data-testid="stMetricValue"] {font-size:1.25rem !important;}
            [data-testid="stMetricLabel"] {font-size:0.75rem !important;}

            /* Shrink tab labels so all four fit without excessive scrolling */
            [data-testid="stTabs"] [data-baseweb="tab"] {
                font-size:0.8rem;
                padding:0.4rem 0.6rem;
            }

            /* Legacy selectors kept for older Streamlit builds */
            .stColumns > div, .css-1lcbmhc > div {width:100% !important; display:block !important;}
            .stMetric, .stMetric > div {flex-direction:column !important; align-items:flex-start !important;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_responsive_ui()


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    agents = pd.read_csv(os.path.join(DATA_DIR, "agents.csv"), parse_dates=["registration_date"])
    customers = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"), parse_dates=["registration_date"])
    txns = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv.gz"), parse_dates=["timestamp"])
    txns = txns.sort_values("timestamp").reset_index(drop=True)
    return agents, customers, txns


@st.cache_data
def load_ground_truth():
    path = os.path.join(DATA_DIR, "fraud_ground_truth.csv.gz")
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


# ---------------------------------------------------------------------------
# Rule-based fraud detection (pandas port of the dbt SQL rules)
# ---------------------------------------------------------------------------
KYC_LIMITS = {"tier_1": 1000, "tier_2": 10000, "tier_3": 100000}


def flag_velocity(txns, min_txns=4, window_minutes=20):
    flags = []
    for cust_id, grp in txns.groupby("customer_id"):
        grp = grp.sort_values("timestamp")
        times = grp["timestamp"].values
        ids = grp["transaction_id"].values
        for i in range(len(times)):
            window_end = times[i] + pd.Timedelta(minutes=window_minutes)
            count_in_window = ((times >= times[i]) & (times <= window_end)).sum()
            if count_in_window >= min_txns:
                sev = "high" if count_in_window >= min_txns * 2 else "medium"
                flags.append((ids[i], "velocity_cycling", sev, int(count_in_window)))
    return pd.DataFrame(flags, columns=["transaction_id", "fraud_pattern", "severity", "rule_metric"])


def flag_structuring(txns, customers, min_split=3, window_minutes=60, near_limit_pct=0.80):
    p2p = txns[txns["txn_type"] == "p2p_transfer"].merge(
        customers[["customer_id", "kyc_tier"]], on="customer_id", how="left"
    )
    p2p["limit"] = p2p["kyc_tier"].map(KYC_LIMITS)
    near = p2p[(p2p["amount"] >= p2p["limit"] * near_limit_pct) & (p2p["amount"] <= p2p["limit"])]

    flags = []
    for cust_id, grp in near.groupby("customer_id"):
        grp = grp.sort_values("timestamp")
        times = grp["timestamp"].values
        ids = grp["transaction_id"].values
        for i in range(len(times)):
            window_end = times[i] + pd.Timedelta(minutes=window_minutes)
            count_in_window = ((times >= times[i]) & (times <= window_end)).sum()
            if count_in_window >= min_split:
                sev = "high" if count_in_window >= min_split * 2 else "medium"
                flags.append((ids[i], "structuring", sev, int(count_in_window)))
    return pd.DataFrame(flags, columns=["transaction_id", "fraud_pattern", "severity", "rule_metric"])


def flag_agent_imbalance(txns, agents, ratio_threshold=3.0):
    agent_txns = txns[txns["agent_id"].notna()].copy()
    agent_txns["txn_date"] = agent_txns["timestamp"].dt.date
    daily = agent_txns.pivot_table(
        index=["agent_id", "txn_date"], columns="txn_type", values="amount", aggfunc="sum", fill_value=0
    ).reset_index()
    for col in ["cash_in", "cash_out"]:
        if col not in daily.columns:
            daily[col] = 0
    daily["ratio"] = daily["cash_out"] / daily["cash_in"].replace(0, pd.NA)
    flagged = daily[(daily["cash_in"] == 0) | (daily["ratio"] >= ratio_threshold)].copy()
    flagged["severity"] = flagged["ratio"].apply(
        lambda r: "high" if pd.notna(r) and r >= ratio_threshold * 2 else "medium"
    )
    return flagged.merge(agents[["agent_id", "region", "tier"]], on="agent_id", how="left")


def flag_geo_impossible(txns, max_window_minutes=45):
    flags = []
    agent_txns = txns[txns["agent_id"].notna()]
    for cust_id, grp in agent_txns.groupby("customer_id"):
        grp = grp.sort_values("timestamp").reset_index(drop=True)
        for i in range(len(grp) - 1):
            for j in range(i + 1, len(grp)):
                gap = (grp.loc[j, "timestamp"] - grp.loc[i, "timestamp"]).total_seconds() / 60
                if gap > max_window_minutes:
                    break
                if grp.loc[i, "region"] != grp.loc[j, "region"]:
                    sev = "high" if gap <= max_window_minutes / 2 else "medium"
                    flags.append((grp.loc[j, "transaction_id"], "geo_impossible", sev, round(gap, 1)))
                    break
    return pd.DataFrame(flags, columns=["transaction_id", "fraud_pattern", "severity", "rule_metric"])


@st.cache_data
def compute_all_flags(txns, customers, agents):
    velocity = flag_velocity(txns)
    structuring = flag_structuring(txns, customers)
    geo = flag_geo_impossible(txns)
    combined = pd.concat([velocity, structuring, geo], ignore_index=True)
    return combined


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("📱 Mobile Money Fraud Analytics")
st.caption("Synthetic dataset modeled on West African mobile money agent-network patterns")

agents, customers, txns = load_data()
ground_truth = load_ground_truth()

with st.spinner("Scoring transactions against detection rules..."):
    flags = compute_all_flags(txns, customers, agents)
    agent_imbalance = flag_agent_imbalance(txns, agents)

alert_summary = (
    flags.groupby("transaction_id")
    .agg(rules_tripped=("fraud_pattern", "nunique"), patterns=("fraud_pattern", lambda x: ", ".join(sorted(set(x)))))
    .reset_index()
    .merge(txns, on="transaction_id", how="left")
    .sort_values("rules_tripped", ascending=False)
)

# ---- Top KPIs --------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total transactions", f"{len(txns):,}")
col2.metric("Flagged transactions", f"{alert_summary['transaction_id'].nunique():,}")
col3.metric("Flag rate", f"{alert_summary['transaction_id'].nunique() / len(txns):.2%}")
col4.metric("Agent imbalance alerts", f"{len(agent_imbalance):,}")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs(
    ["🚨 Fraud Alert Queue", "📈 Transaction Trends", "🏪 Agent Health", "✅ Model Validation"]
)

# ---- Tab 1: Alert queue ----------------------------------------------
with tab1:
    st.subheader("Alert review queue")
    st.caption("Sorted by number of independent rules tripped — the strongest signal.")
    display_cols = ["transaction_id", "timestamp", "customer_id", "txn_type", "amount", "region", "rules_tripped", "patterns"]
    st.dataframe(alert_summary[display_cols].head(200), use_container_width=True, height=420)

    pattern_counts = flags["fraud_pattern"].value_counts().reset_index()
    pattern_counts.columns = ["fraud_pattern", "count"]
    fig = px.bar(pattern_counts, x="fraud_pattern", y="count", title="Alerts by rule")
    st.plotly_chart(fig, use_container_width=True)

# ---- Tab 2: Trends -----------------------------------------------------
with tab2:
    st.subheader("Daily transaction volume")
    daily = txns.copy()
    daily["txn_date"] = daily["timestamp"].dt.date
    daily_agg = daily.groupby(["txn_date", "txn_type"]).size().reset_index(name="count")
    fig2 = px.line(daily_agg, x="txn_date", y="count", color="txn_type", title="Transactions per day by type")
    st.plotly_chart(fig2, use_container_width=True)

    region_agg = daily.groupby("region")["amount"].sum().reset_index().sort_values("amount", ascending=False)
    fig3 = px.bar(region_agg, x="region", y="amount", title="Total transaction value by region")
    st.plotly_chart(fig3, use_container_width=True)

# ---- Tab 3: Agent health -----------------------------------------------
with tab3:
    st.subheader("Agent cash-flow imbalance (potential till-tapping)")
    if len(agent_imbalance):
        st.dataframe(
            agent_imbalance[["agent_id", "region", "tier", "txn_date", "cash_in", "cash_out", "ratio", "severity"]]
            .sort_values("ratio", ascending=False),
            use_container_width=True,
        )
    else:
        st.info("No agent imbalance alerts in the current window.")

    agent_txns = txns[txns["agent_id"].notna()].merge(agents[["agent_id", "region"]], on="agent_id", how="left", suffixes=("", "_agent"))
    agent_volume = agent_txns.groupby("agent_id").size().reset_index(name="txn_count").sort_values("txn_count", ascending=False).head(20)
    fig4 = px.bar(agent_volume, x="agent_id", y="txn_count", title="Top 20 agents by transaction volume")
    st.plotly_chart(fig4, use_container_width=True)

# ---- Tab 4: Validation against ground truth -----------------------------
with tab4:
    st.subheader("Detection performance vs. ground truth")
    if ground_truth is not None:
        scored = ground_truth.merge(
            alert_summary[["transaction_id"]].assign(was_flagged=True),
            on="transaction_id",
            how="left",
        )
        scored["was_flagged"] = scored["was_flagged"].fillna(False)

        tp = ((scored["is_fraud"]) & (scored["was_flagged"])).sum()
        fp = ((~scored["is_fraud"]) & (scored["was_flagged"])).sum()
        fn = ((scored["is_fraud"]) & (~scored["was_flagged"])).sum()
        actual_fraud = scored["is_fraud"].sum()

        recall = tp / actual_fraud if actual_fraud else 0
        precision = tp / (tp + fp) if (tp + fp) else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Recall (catch rate)", f"{recall:.1%}")
        c2.metric("Precision", f"{precision:.1%}")
        c3.metric("False positives", f"{fp:,}")

        st.caption(
            "Recall = share of actual fraud caught by at least one rule. "
            "Precision = share of alerts that were actually fraud. "
            "In production, ground truth wouldn't exist — this view only works "
            "because this is a labeled synthetic benchmark used to tune the rules."
        )

        by_pattern = (
            scored[scored["is_fraud"]]
            .groupby("fraud_pattern")
            .agg(actual=("transaction_id", "count"), caught=("was_flagged", "sum"))
            .reset_index()
        )
        by_pattern["recall"] = by_pattern["caught"] / by_pattern["actual"]
        fig5 = px.bar(by_pattern, x="fraud_pattern", y="recall", title="Recall by injected fraud pattern", range_y=[0, 1])
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.warning("fraud_ground_truth.csv.gz not found — run the generator first.")
