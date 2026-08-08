-- RULE 1 — VELOCITY / CYCLING
-- Flags customers with N+ transactions inside a short rolling window.
-- Classic signature of wallet-testing or rapid cash-in -> cash-out laundering.

{% set velocity_txn_threshold = 4 %}   -- min transactions in window to flag
{% set velocity_window_minutes = 20 %} -- rolling window size

with txns as (
    select * from {{ ref('stg_transactions') }}
),

windowed as (
    select
        transaction_id,
        customer_id,
        txn_timestamp,
        amount,
        txn_type,
        count(*) over (
            partition by customer_id
            order by unix_seconds(timestamp(txn_timestamp))
            range between 0 preceding and ({{ velocity_window_minutes }} * 60) following
        ) as txns_in_window
    from txns
)

select
    transaction_id,
    customer_id,
    txn_timestamp,
    'velocity_cycling'          as fraud_pattern,
    txns_in_window              as rule_metric,
    {{ velocity_txn_threshold }} as rule_threshold,
    case
        when txns_in_window >= {{ velocity_txn_threshold * 2 }} then 'high'
        when txns_in_window >= {{ velocity_txn_threshold }}     then 'medium'
    end as severity
from windowed
where txns_in_window >= {{ velocity_txn_threshold }}
