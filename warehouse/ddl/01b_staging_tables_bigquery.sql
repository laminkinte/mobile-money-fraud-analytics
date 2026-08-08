-- ============================================================================
-- BigQuery variant of the staging schema
-- Create dataset first:  bq mk --dataset your-project:raw
--                         bq mk --dataset your-project:eval
-- ============================================================================

CREATE TABLE IF NOT EXISTS `raw.agents` (
    agent_id             STRING NOT NULL,
    agent_name           STRING NOT NULL,
    region               STRING NOT NULL,
    tier                 STRING NOT NULL,
    registration_date    DATE NOT NULL,
    opening_cash_float   NUMERIC NOT NULL,
    loaded_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS `raw.customers` (
    customer_id          STRING NOT NULL,
    kyc_tier              STRING NOT NULL,
    home_region            STRING NOT NULL,
    registration_date      DATE NOT NULL,
    loaded_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS `raw.transactions` (
    transaction_id             STRING NOT NULL,
    txn_timestamp                TIMESTAMP NOT NULL,
    customer_id                   STRING NOT NULL,
    agent_id                      STRING,
    counterparty_customer_id      STRING,
    txn_type                       STRING NOT NULL,
    amount                          NUMERIC NOT NULL,
    region                          STRING NOT NULL,
    loaded_at                       TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(txn_timestamp)
CLUSTER BY customer_id, agent_id;

CREATE TABLE IF NOT EXISTS `eval.fraud_ground_truth` (
    transaction_id   STRING NOT NULL,
    is_fraud         BOOL NOT NULL,
    fraud_pattern    STRING
);

-- ---------------------------------------------------------------------------
-- Load commands (run from shell, repo root):
-- ---------------------------------------------------------------------------
-- bq load --source_format=CSV --skip_leading_rows=1 \
--   your-project:raw.agents data/raw/agents.csv \
--   agent_id:STRING,agent_name:STRING,region:STRING,tier:STRING,registration_date:DATE,opening_cash_float:NUMERIC
--
-- bq load --source_format=CSV --skip_leading_rows=1 \
--   your-project:raw.customers data/raw/customers.csv \
--   customer_id:STRING,kyc_tier:STRING,home_region:STRING,registration_date:DATE
--
-- bq load --source_format=CSV --skip_leading_rows=1 \
--   your-project:raw.transactions data/raw/transactions.csv.gz \
--   transaction_id:STRING,txn_timestamp:TIMESTAMP,customer_id:STRING,agent_id:STRING,counterparty_customer_id:STRING,txn_type:STRING,amount:NUMERIC,region:STRING
--
-- bq load --source_format=CSV --skip_leading_rows=1 \
--   your-project:eval.fraud_ground_truth data/raw/fraud_ground_truth.csv.gz \
--   transaction_id:STRING,is_fraud:BOOLEAN,fraud_pattern:STRING
