"""
Mobile Money Synthetic Data Generator
======================================

Generates a realistic-but-synthetic mobile money dataset (agents, customers,
transactions) with deliberately injected fraud patterns, mirroring the
transaction/agent structure of real West African mobile money operators
(cash-in/cash-out agent network model).

Ground-truth fraud labels are written to a SEPARATE file
(data/raw/fraud_ground_truth.csv.gz) so that downstream detection logic can
be built "blind" and then scored against the truth set — exactly how you'd
evaluate a real fraud model.

Usage:
    python generate_data.py
"""

import csv
import gzip
import os
import random
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import config as cfg

random.seed(cfg.RANDOM_SEED)
np.random.seed(cfg.RANDOM_SEED)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def random_timestamp(start_date, end_date):
    delta_days = (end_date - start_date).days
    day_offset = random.randint(0, delta_days)
    ts = datetime.combine(start_date, datetime.min.time()) + timedelta(days=day_offset)
    # bias transactions toward daytime hours (8am - 9pm)
    hour = int(np.clip(np.random.normal(14, 4), 6, 23))
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return ts.replace(hour=hour, minute=minute, second=second)


def weighted_choice(weights_dict):
    items = list(weights_dict.keys())
    weights = list(weights_dict.values())
    return random.choices(items, weights=weights, k=1)[0]


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------------------
# 1. Generate Agents
# ---------------------------------------------------------------------------
def generate_agents(n_agents):
    agents = []
    for i in range(n_agents):
        agent_id = f"AGT{i:05d}"
        region = random.choice(cfg.REGIONS)
        tier = random.choices(["standard", "super_agent"], weights=[0.85, 0.15], k=1)[0]
        reg_date = cfg.START_DATE - timedelta(days=random.randint(30, 900))
        opening_float = round(random.uniform(5000, 80000), 2) if tier == "standard" else round(random.uniform(50000, 300000), 2)
        agents.append({
            "agent_id": agent_id,
            "agent_name": f"Agent {i:05d}",
            "region": region,
            "tier": tier,
            "registration_date": reg_date.isoformat(),
            "opening_cash_float": opening_float,
        })
    return pd.DataFrame(agents)


# ---------------------------------------------------------------------------
# 2. Generate Customers
# ---------------------------------------------------------------------------
def generate_customers(n_customers):
    customers = []
    for i in range(n_customers):
        customer_id = f"CUS{i:07d}"
        kyc_tier = weighted_choice(cfg.KYC_TIER_WEIGHTS)
        home_region = random.choice(cfg.REGIONS)
        reg_date = cfg.START_DATE - timedelta(days=random.randint(1, 1200))
        customers.append({
            "customer_id": customer_id,
            "kyc_tier": kyc_tier,
            "home_region": home_region,
            "registration_date": reg_date.isoformat(),
        })
    return pd.DataFrame(customers)


# ---------------------------------------------------------------------------
# 3. Baseline (legitimate) transaction generation
# ---------------------------------------------------------------------------
def generate_baseline_transactions(customers_df, agents_df):
    txns = []
    agents_by_region = agents_df.groupby("region")["agent_id"].apply(list).to_dict()
    all_customer_ids = customers_df["customer_id"].tolist()
    n_days = (cfg.END_DATE - cfg.START_DATE).days + 1

    for _, cust in customers_df.iterrows():
        expected_txns = np.random.poisson(cfg.AVG_TXN_PER_CUSTOMER_PER_DAY * n_days)
        limit = cfg.KYC_TIERS[cust["kyc_tier"]]["single_txn_limit"]

        for _ in range(expected_txns):
            txn_type = weighted_choice(cfg.TXN_TYPE_WEIGHTS)
            ts = random_timestamp(cfg.START_DATE, cfg.END_DATE)
            amount = round(min(np.random.exponential(limit * 0.15), limit), 2)
            amount = max(amount, 20.0)

            region_agents = agents_by_region.get(cust["home_region"], agents_df["agent_id"].tolist())
            agent_id = random.choice(region_agents) if txn_type in ("cash_in", "cash_out") else None
            counterparty = random.choice(all_customer_ids) if txn_type == "p2p_transfer" else None

            txns.append({
                "transaction_id": new_id("TXN"),
                "timestamp": ts.isoformat(),
                "customer_id": cust["customer_id"],
                "agent_id": agent_id,
                "counterparty_customer_id": counterparty,
                "txn_type": txn_type,
                "amount": amount,
                "region": cust["home_region"],
                "is_fraud": False,
                "fraud_pattern": None,
            })
    return txns


# ---------------------------------------------------------------------------
# 4. Fraud pattern injection
# ---------------------------------------------------------------------------
def inject_cycling(customers_df, agents_df):
    """Rapid cash-in -> cash-out bursts (wash cycling)."""
    fp = cfg.FRAUD_PATTERNS["cycling"]
    n_targets = max(1, int(len(customers_df) * fp["customer_rate"]))
    targets = customers_df.sample(n=n_targets, random_state=cfg.RANDOM_SEED)
    txns = []
    for _, cust in targets.iterrows():
        burst_len = random.randint(*fp["burst_txn_count"])
        base_ts = random_timestamp(cfg.START_DATE, cfg.END_DATE)
        region_agents = agents_df[agents_df["region"] == cust["home_region"]]["agent_id"].tolist() or agents_df["agent_id"].tolist()
        amount = round(random.uniform(2000, 20000), 2)
        for j in range(burst_len):
            ts = base_ts + timedelta(minutes=random.randint(0, fp["burst_window_minutes"]))
            txn_type = "cash_in" if j % 2 == 0 else "cash_out"
            txns.append({
                "transaction_id": new_id("TXN"),
                "timestamp": ts.isoformat(),
                "customer_id": cust["customer_id"],
                "agent_id": random.choice(region_agents),
                "counterparty_customer_id": None,
                "txn_type": txn_type,
                "amount": amount,
                "region": cust["home_region"],
                "is_fraud": True,
                "fraud_pattern": "cycling",
            })
    return txns


def inject_structuring(customers_df):
    """Split a large transfer into multiple sub-limit transactions."""
    fp = cfg.FRAUD_PATTERNS["structuring"]
    n_targets = max(1, int(len(customers_df) * fp["customer_rate"]))
    targets = customers_df.sample(n=n_targets, random_state=cfg.RANDOM_SEED + 1)
    all_customer_ids = customers_df["customer_id"].tolist()
    txns = []
    for _, cust in targets.iterrows():
        limit = cfg.KYC_TIERS[cust["kyc_tier"]]["single_txn_limit"]
        split_count = random.randint(*fp["split_count"])
        base_ts = random_timestamp(cfg.START_DATE, cfg.END_DATE)
        per_txn_amount = round(limit * random.uniform(0.85, 0.98), 2)  # just under limit
        counterparty = random.choice(all_customer_ids)
        for j in range(split_count):
            ts = base_ts + timedelta(minutes=random.randint(0, fp["split_window_minutes"]))
            txns.append({
                "transaction_id": new_id("TXN"),
                "timestamp": ts.isoformat(),
                "customer_id": cust["customer_id"],
                "agent_id": None,
                "counterparty_customer_id": counterparty,
                "txn_type": "p2p_transfer",
                "amount": per_txn_amount,
                "region": cust["home_region"],
                "is_fraud": True,
                "fraud_pattern": "structuring",
            })
    return txns


def inject_takeover(customers_df, agents_df):
    """Dormant account suddenly reactivated with a burst of activity (SIM-swap style)."""
    fp = cfg.FRAUD_PATTERNS["takeover"]
    n_targets = max(1, int(len(customers_df) * fp["customer_rate"]))
    targets = customers_df.sample(n=n_targets, random_state=cfg.RANDOM_SEED + 2)
    txns = []
    for _, cust in targets.iterrows():
        reactivation_day = cfg.START_DATE + timedelta(
            days=random.randint(fp["dormancy_days_min"], (cfg.END_DATE - cfg.START_DATE).days)
        )
        txn_count = random.randint(*fp["reactivation_txn_count"])
        region_agents = agents_df[agents_df["region"] == cust["home_region"]]["agent_id"].tolist() or agents_df["agent_id"].tolist()
        for _ in range(txn_count):
            ts = datetime.combine(reactivation_day, datetime.min.time()) + timedelta(
                minutes=random.randint(0, 180)
            )
            txn_type = random.choice(["cash_out", "p2p_transfer"])
            txns.append({
                "transaction_id": new_id("TXN"),
                "timestamp": ts.isoformat(),
                "customer_id": cust["customer_id"],
                "agent_id": random.choice(region_agents) if txn_type == "cash_out" else None,
                "counterparty_customer_id": random.choice(customers_df["customer_id"].tolist()) if txn_type == "p2p_transfer" else None,
                "txn_type": txn_type,
                "amount": round(random.uniform(3000, 25000), 2),
                "region": cust["home_region"],
                "is_fraud": True,
                "fraud_pattern": "takeover",
            })
    return txns


def inject_agent_imbalance(agents_df, customers_df):
    """Agent whose cash-out volume vastly exceeds cash-in (till-tapping)."""
    fp = cfg.FRAUD_PATTERNS["agent_imbalance"]
    n_targets = max(1, int(len(agents_df) * fp["agent_rate"]))
    targets = agents_df.sample(n=n_targets, random_state=cfg.RANDOM_SEED + 3)
    txns = []
    for _, agent in targets.iterrows():
        local_customers = customers_df[customers_df["home_region"] == agent["region"]]["customer_id"].tolist() \
            or customers_df["customer_id"].tolist()
        for _ in range(random.randint(15, 30)):
            ts = random_timestamp(cfg.START_DATE, cfg.END_DATE)
            txns.append({
                "transaction_id": new_id("TXN"),
                "timestamp": ts.isoformat(),
                "customer_id": random.choice(local_customers),
                "agent_id": agent["agent_id"],
                "counterparty_customer_id": None,
                "txn_type": "cash_out",
                "amount": round(random.uniform(5000, 40000), 2),
                "region": agent["region"],
                "is_fraud": True,
                "fraud_pattern": "agent_imbalance",
            })
    return txns


def inject_geo_impossible(customers_df, agents_df):
    """Same customer transacts in two distant regions within an implausible window."""
    fp = cfg.FRAUD_PATTERNS["geo_impossible"]
    n_targets = max(1, int(len(customers_df) * fp["customer_rate"]))
    targets = customers_df.sample(n=n_targets, random_state=cfg.RANDOM_SEED + 4)
    txns = []
    for _, cust in targets.iterrows():
        ts1 = random_timestamp(cfg.START_DATE, cfg.END_DATE)
        ts2 = ts1 + timedelta(minutes=random.randint(1, fp["max_window_minutes"]))
        region_a, region_b = random.sample(cfg.REGIONS, 2)
        agent_a = agents_df[agents_df["region"] == region_a]["agent_id"].sample(1).iloc[0]
        agent_b = agents_df[agents_df["region"] == region_b]["agent_id"].sample(1).iloc[0]
        for ts, region, agent_id in [(ts1, region_a, agent_a), (ts2, region_b, agent_b)]:
            txns.append({
                "transaction_id": new_id("TXN"),
                "timestamp": ts.isoformat(),
                "customer_id": cust["customer_id"],
                "agent_id": agent_id,
                "counterparty_customer_id": None,
                "txn_type": "cash_out",
                "amount": round(random.uniform(2000, 15000), 2),
                "region": region,
                "is_fraud": True,
                "fraud_pattern": "geo_impossible",
            })
    return txns


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    print("Generating agents...")
    agents_df = generate_agents(cfg.N_AGENTS)

    print("Generating customers...")
    customers_df = generate_customers(cfg.N_CUSTOMERS)

    print("Generating baseline (legitimate) transactions...")
    baseline_txns = generate_baseline_transactions(customers_df, agents_df)

    print("Injecting fraud patterns...")
    fraud_txns = []
    fraud_txns += inject_cycling(customers_df, agents_df)
    fraud_txns += inject_structuring(customers_df)
    fraud_txns += inject_takeover(customers_df, agents_df)
    fraud_txns += inject_agent_imbalance(agents_df, customers_df)
    fraud_txns += inject_geo_impossible(customers_df, agents_df)

    all_txns = baseline_txns + fraud_txns
    txns_df = pd.DataFrame(all_txns).sort_values("timestamp").reset_index(drop=True)

    print(f"  {len(baseline_txns):,} legitimate transactions")
    print(f"  {len(fraud_txns):,} fraudulent transactions across {len(cfg.FRAUD_PATTERNS)} patterns")
    print(f"  {len(txns_df):,} total transactions")

    # ---- Write outputs -----------------------------------------------
    agents_path = os.path.join(cfg.OUTPUT_DIR, "agents.csv")
    customers_path = os.path.join(cfg.OUTPUT_DIR, "customers.csv")
    agents_df.to_csv(agents_path, index=False)
    customers_df.to_csv(customers_path, index=False)

    # Full transactions (WITH fraud labels) — used for model validation only
    full_txn_path = os.path.join(cfg.OUTPUT_DIR, "transactions_with_labels.csv.gz")
    txns_df.to_csv(full_txn_path, index=False, compression="gzip")

    # "Production" transactions feed — labels stripped, exactly what an
    # analyst pipeline would actually receive in the real world.
    prod_cols = [c for c in txns_df.columns if c not in ("is_fraud", "fraud_pattern")]
    prod_path = os.path.join(cfg.OUTPUT_DIR, "transactions.csv.gz")
    txns_df[prod_cols].to_csv(prod_path, index=False, compression="gzip")

    # Ground truth kept separate, joinable on transaction_id — for scoring
    # your detection logic after the fact.
    truth_path = os.path.join(cfg.OUTPUT_DIR, "fraud_ground_truth.csv.gz")
    txns_df[["transaction_id", "is_fraud", "fraud_pattern"]].to_csv(
        truth_path, index=False, compression="gzip"
    )

    print("\nFiles written to data/raw/:")
    for p in [agents_path, customers_path, prod_path, truth_path]:
        print(f"  - {p}")
    print("\n(transactions_with_labels.csv.gz kept for convenience but is NOT")
    print(" what a real fraud pipeline would see — use transactions.csv.gz +")
    print(" ground truth only when scoring your detection logic.)")


if __name__ == "__main__":
    main()
