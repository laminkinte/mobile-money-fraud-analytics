-- ============================================================================
-- Load raw CSV/gzip exports into staging tables (PostgreSQL \copy examples)
-- Run from psql, with working directory = repo root, e.g.:
--   psql -d mobile_money -f warehouse/ddl/01_staging_tables.sql
--   psql -d mobile_money -c "\copy raw.agents FROM PROGRAM 'cat data/raw/agents.csv' CSV HEADER"
-- Below are the equivalent \copy commands for reference / a load script.
-- ============================================================================

\copy raw.agents (agent_id, agent_name, region, tier, registration_date, opening_cash_float) \
    FROM 'data/raw/agents.csv' WITH (FORMAT csv, HEADER true);

\copy raw.customers (customer_id, kyc_tier, home_region, registration_date) \
    FROM 'data/raw/customers.csv' WITH (FORMAT csv, HEADER true);

-- transactions.csv.gz is gzip-compressed — pipe through zcat/gunzip
\copy raw.transactions (transaction_id, txn_timestamp, customer_id, agent_id, counterparty_customer_id, txn_type, amount, region) \
    FROM PROGRAM 'zcat data/raw/transactions.csv.gz' WITH (FORMAT csv, HEADER true);

-- ground truth (evaluation schema only)
\copy eval.fraud_ground_truth (transaction_id, is_fraud, fraud_pattern) \
    FROM PROGRAM 'zcat data/raw/fraud_ground_truth.csv.gz' WITH (FORMAT csv, HEADER true);
