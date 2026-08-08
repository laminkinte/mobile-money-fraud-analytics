-- TRANSACTION VELOCITY (DAILY)
-- Daily transaction volume and value by type and region — the baseline
-- trend view a fraud analyst checks before drilling into alerts.

select
    txn_date,
    region,
    txn_type,
    count(*)                       as txn_count,
    sum(amount)                    as total_amount,
    round(avg(amount), 2)          as avg_amount,
    count(distinct customer_id)    as unique_customers
from {{ ref('stg_transactions') }}
group by txn_date, region, txn_type
