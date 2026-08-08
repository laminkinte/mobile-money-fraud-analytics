"""
Configuration for the Mobile Money Synthetic Data Generator.

Tune volumes and fraud injection rates here without touching generator logic.
Defaults are sized to mimic a mid-size West African mobile money operator
(loosely modeled on patterns observed in Gambia/Nigeria markets).
"""

from datetime import date

# ---------------------------------------------------------------------------
# Simulation window
# ---------------------------------------------------------------------------
START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 2, 28)          # 59-day simulation window

# ---------------------------------------------------------------------------
# Population sizes
# ---------------------------------------------------------------------------
N_AGENTS = 150                        # active mobile money agents
N_CUSTOMERS = 6_000                   # registered wallet holders
AVG_TXN_PER_CUSTOMER_PER_DAY = 0.30   # baseline transaction frequency

# ---------------------------------------------------------------------------
# Geography (simplified region list — swap for real region names as needed)
# ---------------------------------------------------------------------------
REGIONS = [
    "Banjul", "Kanifing", "Brikama", "Farafenni", "Basse",   # Gambia
    "Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt",     # Nigeria
]

# ---------------------------------------------------------------------------
# Transaction types and their baseline mix (must sum to 1.0)
# ---------------------------------------------------------------------------
TXN_TYPE_WEIGHTS = {
    "cash_in": 0.30,
    "cash_out": 0.30,
    "p2p_transfer": 0.25,
    "bill_pay": 0.10,
    "airtime_topup": 0.05,
}

# KYC tiers and their transaction limits (local currency units, generic)
KYC_TIERS = {
    "tier_1": {"daily_limit": 5_000,   "single_txn_limit": 1_000},
    "tier_2": {"daily_limit": 50_000,  "single_txn_limit": 10_000},
    "tier_3": {"daily_limit": 500_000, "single_txn_limit": 100_000},
}
KYC_TIER_WEIGHTS = {"tier_1": 0.55, "tier_2": 0.35, "tier_3": 0.10}

# ---------------------------------------------------------------------------
# Fraud injection rates — fraction of customers/agents assigned each pattern
# Keep these low and realistic; the point is a needle-in-haystack problem.
# ---------------------------------------------------------------------------
FRAUD_PATTERNS = {
    # Rapid cash-in then cash-out to launder / test stolen wallet access
    "cycling": {
        "customer_rate": 0.006,     # 0.6% of customers exhibit this
        "burst_txn_count": (4, 9),  # transactions per burst
        "burst_window_minutes": 20,
    },
    # Splitting a large transfer into several sub-limit transactions
    "structuring": {
        "customer_rate": 0.004,
        "split_count": (3, 6),
        "split_window_minutes": 60,
    },
    # SIM-swap style takeover: dormant wallet suddenly very active
    "takeover": {
        "customer_rate": 0.003,
        "dormancy_days_min": 30,
        "reactivation_txn_count": (5, 12),
    },
    # Agent till-tapping: agent's cash-out volume far exceeds cash-in float
    "agent_imbalance": {
        "agent_rate": 0.02,         # 2% of agents
        "imbalance_ratio_min": 3.0, # cash-out at least 3x cash-in
    },
    # Geographic impossibility: same customer, two distant agents, short window
    "geo_impossible": {
        "customer_rate": 0.003,
        "max_window_minutes": 45,   # too fast to physically travel between regions
    },
}

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
OUTPUT_DIR = "../data/raw"
GZIP_OUTPUT = True   # mirrors the gzip-compressed export format from real ops
