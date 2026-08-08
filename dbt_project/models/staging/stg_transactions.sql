-- Light cleaning/typing pass over raw.transactions. One row per transaction.
-- Deduplicates on transaction_id defensively (real feeds occasionally
-- redeliver rows) and derives a few timestamp parts used across marts.

with dedup as (
    select
        *,
        row_number() over (
            partition by transaction_id order by loaded_at desc
        ) as rn
    from {{ source('raw', 'transactions') }}
)

select
    transaction_id,
    txn_timestamp,
    date(txn_timestamp)                as txn_date,
    extract(hour from txn_timestamp)   as txn_hour,
    customer_id,
    agent_id,
    counterparty_customer_id,
    txn_type,
    amount,
    region
from dedup
where rn = 1
