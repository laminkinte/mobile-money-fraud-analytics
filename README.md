# Mobile Money Fraud Analytics

An end-to-end fraud analytics pipeline modeled on West African mobile money
agent-network operators (Gambia/Nigeria market patterns): synthetic data
generation → warehouse ingestion → dbt transformation → rule-based fraud
detection → analyst dashboard, with detection performance scored against
withheld ground truth.

Built to demonstrate the full data analyst → data engineer workflow on a
realistic fintech problem, drawing on prior work auditing mobile money
transaction data for a live operator.

## Why this project

Mobile money is the dominant payment rail across much of West Africa, and
agent-network fraud (till-tapping, wallet cycling, SIM-swap takeovers) is a
real, costly problem for operators. This project builds the kind of
detection + monitoring layer a fintech data team would actually own —
using synthetic data so it's shareable without exposing any real
operator's transaction data.

## Architecture

```
generator/              Synthetic data generator (agents, customers,
                         transactions) with 5 injected fraud patterns
                         and a withheld ground-truth label set
        │
        ▼
data/raw/                agents.csv, customers.csv, transactions.csv.gz
                         (production feed — NO fraud labels included)
        │
        ▼
warehouse/ddl/           Staging schema (Postgres + BigQuery variants)
                         and load scripts
        │
        ▼
dbt_project/              staging/  → cleaned, typed, deduplicated
                         fraud/    → 5 rule-based detection models +
                                     unified alert queue + evaluation
                         marts/    → dimensional model + agent health +
                                     transaction velocity + alert summary
        │
        ▼
dashboard/app.py          Streamlit analyst dashboard: alert queue,
                         trends, agent health, detection performance
```

## Fraud patterns modeled

| Pattern | Signature | Detection rule |
|---|---|---|
| **Cycling** | Rapid cash-in → cash-out bursts (wallet testing / laundering) | 4+ transactions within a 20-minute rolling window |
| **Structuring** | Splitting a transfer into sub-limit pieces to dodge reporting thresholds | 3+ near-limit P2P transfers within 60 minutes |
| **Agent imbalance** | Cash-out volume far exceeding cash-in (till-tapping) | Daily cash-out ≥ 3x cash-in per agent |
| **Geographic impossibility** | Same customer active in two distant regions too fast | Cross-region transactions within 45 minutes |
| **Dormant reactivation** | 30+ day dormant wallet suddenly reactivated (SIM-swap) | Burst of 5+ transactions within 3 hours of reactivation |

All thresholds live in `generator/config.py` (injection side) and are
mirrored at the top of each `dbt_project/models/fraud/fr_*.sql` file
(detection side) — intentionally kept separate so detection is tuned
"blind," then scored.

## Quickstart

```bash
# 1. Generate the synthetic dataset (~106k transactions, ~2 min)
cd generator
pip install -r ../requirements.txt
python generate_data.py

# 2. Load into a warehouse (Postgres example)
psql -d mobile_money -f ../warehouse/ddl/01_staging_tables.sql
psql -d mobile_money -f ../warehouse/ddl/02_load_staging_postgres.sql

# 3. Run the dbt transformation + fraud detection layer
cd ../dbt_project
cp profiles.yml.example ~/.dbt/profiles.yml   # fill in credentials
dbt run
dbt test

# 4. Launch the analyst dashboard (no warehouse required — reads data/raw directly)
cd ..
streamlit run dashboard/app.py
```

For BigQuery instead of Postgres, use `warehouse/ddl/01b_staging_tables_bigquery.sql`
and the `bigquery` target in `profiles.yml.example`.

## Detection performance

Because ground truth is withheld from the production feed and kept
separately (`data/raw/fraud_ground_truth.csv.gz` / `eval.fraud_ground_truth`),
the rule set can be scored exactly like a real model evaluation:

- `dbt_project/models/fraud/fraud_rule_evaluation.sql` — overall precision/recall
- Dashboard → **Model Validation** tab — recall broken down by fraud pattern

This mirrors how you'd actually defend a rule-based detection system to a
risk team: show what it catches, what it misses, and the false-positive
cost of tightening it further.

## Design notes

- **Rules before ML.** The detection layer is rule-based and explainable —
  which is what real mobile money operators deploy first, since every
  alert needs to be defensible to a compliance team. An ML layer (Isolation
  Forest / logistic regression on the same features) is a natural next
  iteration, but starting with auditable rules is the realistic choice.
- **Ground truth is synthetic-only.** The `eval` schema and
  `fraud_rule_evaluation` model exist only because this is a labeled
  benchmark dataset built for this project — a real production pipeline
  would never have this table. It's here purely to demonstrate and tune
  detection quality.
- **SQL targets BigQuery syntax** (`date_diff`, `timestamp_diff`, `qualify`,
  `safe_divide`). Postgres equivalents are straightforward swaps
  (`age()`/date arithmetic, `DISTINCT ON` instead of `QUALIFY`, manual
  NULLIF instead of `SAFE_DIVIDE`) — noted inline where it matters.
- **Agent imbalance thresholds need real tuning.** With small daily
  transaction counts per agent, cash-in/cash-out ratios are naturally
  noisy — in a real deployment this rule would be calibrated against
  actual false-positive tolerance, not left at a fixed 3x cutoff. Included
  as-is deliberately, since threshold tuning is itself part of the analyst
  workflow worth showing.

## Repo structure

```
mobile-money-fraud-analytics/
├── generator/              synthetic data generation
├── data/raw/                generated CSV/gzip output
├── warehouse/ddl/            staging schema (Postgres + BigQuery)
├── dbt_project/               staging / fraud / marts models
├── dashboard/                 Streamlit analyst dashboard
├── requirements.txt
└── README.md
```

## Stack

Python (pandas, numpy) · SQL (Postgres / BigQuery) · dbt · Streamlit · Plotly
