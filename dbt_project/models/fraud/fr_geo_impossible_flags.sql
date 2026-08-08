-- RULE 4 — GEOGRAPHIC IMPOSSIBILITY
-- Flags a customer transacting through agents in two different regions
-- within a window too short for plausible physical travel.

{% set max_travel_minutes = 45 %}

with agent_txns as (
    select
        t.transaction_id,
        t.customer_id,
        t.txn_timestamp,
        t.region,
        t.agent_id
    from {{ ref('stg_transactions') }} t
    where t.agent_id is not null
),

paired as (
    select
        a.transaction_id,
        a.customer_id,
        a.txn_timestamp          as first_txn_ts,
        a.region                 as first_region,
        b.transaction_id         as next_transaction_id,
        b.txn_timestamp          as next_txn_ts,
        b.region                 as next_region,
        timestamp_diff(timestamp(b.txn_timestamp), timestamp(a.txn_timestamp), minute) as minutes_between
    from agent_txns a
    join agent_txns b
        on a.customer_id = b.customer_id
        and b.txn_timestamp > a.txn_timestamp
        and a.region != b.region
    qualify row_number() over (
        partition by a.transaction_id order by b.txn_timestamp asc
    ) = 1
)

select
    next_transaction_id       as transaction_id,
    customer_id,
    next_txn_ts               as txn_timestamp,
    'geo_impossible'          as fraud_pattern,
    minutes_between           as rule_metric,
    {{ max_travel_minutes }}  as rule_threshold,
    case
        when minutes_between <= {{ max_travel_minutes // 2 }} then 'high'
        when minutes_between <= {{ max_travel_minutes }}      then 'medium'
    end as severity
from paired
where minutes_between <= {{ max_travel_minutes }}
