-- RULE 5 — DORMANT ACCOUNT REACTIVATION (SIM-swap / takeover)
-- Flags accounts with no activity for 30+ days that suddenly generate
-- a burst of high-value or high-frequency transactions.

{% set dormancy_days = 30 %}
{% set reactivation_burst_count = 5 %}
{% set reactivation_window_hours = 3 %}

with txns as (
    select
        transaction_id,
        customer_id,
        txn_timestamp,
        amount
    from {{ ref('stg_transactions') }}
),

with_gap as (
    select
        *,
        date_diff(
            date(txn_timestamp),
            date(lag(txn_timestamp) over (partition by customer_id order by txn_timestamp)),
            day
        ) as days_since_last_txn
    from txns
),

reactivations as (
    select * from with_gap
    where days_since_last_txn >= {{ dormancy_days }}
),

burst_check as (
    select
        r.transaction_id,
        r.customer_id,
        r.txn_timestamp,
        r.days_since_last_txn,
        count(t.transaction_id) over (
            partition by r.customer_id, r.transaction_id
        ) as burst_txns
    from reactivations r
    join txns t
        on t.customer_id = r.customer_id
        and t.txn_timestamp between r.txn_timestamp
            and timestamp_add(timestamp(r.txn_timestamp), interval {{ reactivation_window_hours }} hour)
)

select
    transaction_id,
    customer_id,
    txn_timestamp,
    'dormant_reactivation'          as fraud_pattern,
    days_since_last_txn             as rule_metric,
    {{ dormancy_days }}             as rule_threshold,
    case
        when days_since_last_txn >= {{ dormancy_days * 2 }} then 'high'
        else 'medium'
    end as severity
from burst_check
where burst_txns >= {{ reactivation_burst_count }}
