-- FRAUD ALERT QUEUE
-- Unions every rule's output into one analyst-facing queue, enriched with
-- customer/agent context. A transaction can appear once per rule it trips
-- (a transaction tripping 2 rules is a stronger signal, surfaced via
-- alert_count in the review view below).

with velocity as (
    select transaction_id, customer_id, txn_timestamp, fraud_pattern, severity
    from {{ ref('fr_velocity_flags') }}
),

structuring as (
    select transaction_id, customer_id, txn_timestamp, fraud_pattern, severity
    from {{ ref('fr_structuring_flags') }}
),

geo as (
    select transaction_id, customer_id, txn_timestamp, fraud_pattern, severity
    from {{ ref('fr_geo_impossible_flags') }}
),

dormant as (
    select transaction_id, customer_id, txn_timestamp, fraud_pattern, severity
    from {{ ref('fr_dormant_reactivation_flags') }}
),

all_alerts as (
    select * from velocity
    union all
    select * from structuring
    union all
    select * from geo
    union all
    select * from dormant
)

select
    a.transaction_id,
    a.customer_id,
    a.txn_timestamp,
    a.fraud_pattern,
    a.severity,
    t.txn_type,
    t.amount,
    t.region,
    t.agent_id,
    c.kyc_tier,
    c.account_age_days,
    'open'          as review_status,      -- open | confirmed_fraud | false_positive
    current_timestamp() as alert_created_at
from all_alerts a
join {{ ref('stg_transactions') }} t using (transaction_id)
join {{ ref('stg_customers') }} c using (customer_id)
