-- ============================================================================
-- Mobile Money Fraud Analytics — Staging DDL
-- ============================================================================
-- Target: PostgreSQL by default. For BigQuery, swap:
--   SERIAL          -> remove (BQ has no auto-increment; use GENERATE_UUID())
--   TIMESTAMP       -> TIMESTAMP (compatible)
--   NUMERIC(14,2)   -> NUMERIC (compatible)
--   TEXT            -> STRING
--   BOOLEAN         -> BOOL
-- A BigQuery variant is provided in 01b_staging_tables_bigquery.sql
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS raw;

-- ----------------------------------------------------------------------------
-- raw.agents  — mirrors generator/data/raw/agents.csv
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.agents (
    agent_id             TEXT PRIMARY KEY,
    agent_name           TEXT NOT NULL,
    region               TEXT NOT NULL,
    tier                 TEXT NOT NULL,          -- 'standard' | 'super_agent'
    registration_date    DATE NOT NULL,
    opening_cash_float   NUMERIC(14, 2) NOT NULL,
    loaded_at            TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- raw.customers — mirrors generator/data/raw/customers.csv
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id          TEXT PRIMARY KEY,
    kyc_tier              TEXT NOT NULL,          -- 'tier_1' | 'tier_2' | 'tier_3'
    home_region           TEXT NOT NULL,
    registration_date     DATE NOT NULL,
    loaded_at             TIMESTAMP NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- raw.transactions — mirrors generator/data/raw/transactions.csv.gz
-- NOTE: this is the "production" feed — NO fraud labels included, exactly
-- as a real ingestion pipeline would receive it.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.transactions (
    transaction_id           TEXT PRIMARY KEY,
    txn_timestamp             TIMESTAMP NOT NULL,
    customer_id                TEXT NOT NULL REFERENCES raw.customers(customer_id),
    agent_id                   TEXT REFERENCES raw.agents(agent_id),         -- NULL for p2p/bill_pay/airtime
    counterparty_customer_id   TEXT REFERENCES raw.customers(customer_id),   -- NULL unless p2p_transfer
    txn_type                   TEXT NOT NULL,      -- cash_in | cash_out | p2p_transfer | bill_pay | airtime_topup
    amount                      NUMERIC(14, 2) NOT NULL,
    region                      TEXT NOT NULL,
    loaded_at                   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_txn_customer_ts ON raw.transactions (customer_id, txn_timestamp);
CREATE INDEX IF NOT EXISTS idx_txn_agent_ts    ON raw.transactions (agent_id, txn_timestamp);
CREATE INDEX IF NOT EXISTS idx_txn_timestamp   ON raw.transactions (txn_timestamp);

-- ----------------------------------------------------------------------------
-- raw.fraud_ground_truth — held OUTSIDE the analyst-facing schema.
-- Only used offline to score detection rules/models. In a real environment
-- this would never exist; here it's how you validate your own pipeline.
-- ----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS eval;

CREATE TABLE IF NOT EXISTS eval.fraud_ground_truth (
    transaction_id   TEXT PRIMARY KEY,
    is_fraud         BOOLEAN NOT NULL,
    fraud_pattern    TEXT
);
