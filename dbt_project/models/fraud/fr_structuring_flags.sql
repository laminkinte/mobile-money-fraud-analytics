-- RULE 2 — STRUCTURING
-- Flags customers who send several transactions, each just under their
-- KYC single-transaction limit, that together exceed the limit within a
-- short window. Classic technique to dodge reporting thresholds.

{% set structuring_window_minutes = 60 %}
{% set near_limit_pct = 0.80 %}   -- "near limit" = >= 80% of single-txn limit
{% set min_split_count = 3 %}

with txns as (
    select
        t.transaction_id,
        t.customer_id,
        t.txn_timestamp,
        t.amount,
        t.txn_type,
        c.kyc_tier
    from {{ ref('stg_transactions') }} t
    join {{ ref('stg_customers') }} c using (customer_id)
    where t.txn_type = 'p2p_transfer'
),

limits as (
    select *,
        case kyc_tier
            when 'tier_1' then 1000
            when 'tier_2' then 10000
            when 'tier_3' then 100000
        end as single_txn_limit
    from txns
),

near_limit as (
    select *
    from limits
    where amount >= single_txn_limit * {{ near_limit_pct }}
      and amount <= single_txn_limit
),

windowed as (
    select
        transaction_id,
        customer_id,
        txn_timestamp,
        amount,
        count(*) over (
            partition by customer_id
            order by unix_seconds(timestamp(txn_timestamp))
            range between 0 preceding and ({{ structuring_window_minutes }} * 60) following
        ) as splits_in_window,
        sum(amount) over (
            partition by customer_id
            order by unix_seconds(timestamp(txn_timestamp))
            range between 0 preceding and ({{ structuring_window_minutes }} * 60) following
        ) as total_amount_in_window
    from near_limit
)

select
    transaction_id,
    customer_id,
    txn_timestamp,
    'structuring'          as fraud_pattern,
    splits_in_window       as rule_metric,
    {{ min_split_count }}  as rule_threshold,
    case
        when splits_in_window >= {{ min_split_count * 2 }} then 'high'
        when splits_in_window >= {{ min_split_count }}     then 'medium'
    end as severity
from windowed
where splits_in_window >= {{ min_split_count }}
