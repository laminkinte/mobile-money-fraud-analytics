-- AGENT DAILY HEALTH
-- One row per agent per day: cash-in/cash-out volume, transaction count,
-- and whether the day tripped the imbalance (till-tapping) rule.
-- Powers the "Agent Network Health" dashboard view.

with daily_txns as (
    select
        agent_id,
        txn_date,
        sum(case when txn_type = 'cash_in'  then amount else 0 end) as cash_in_amount,
        sum(case when txn_type = 'cash_out' then amount else 0 end) as cash_out_amount,
        count(*) as total_txns,
        count(distinct customer_id) as unique_customers_served
    from {{ ref('stg_transactions') }}
    where agent_id is not null
    group by agent_id, txn_date
),

imbalance as (
    select agent_id, txn_date, severity as imbalance_severity
    from {{ ref('fr_agent_imbalance_flags') }}
)

select
    d.agent_id,
    ag.region,
    ag.tier,
    d.txn_date,
    d.cash_in_amount,
    d.cash_out_amount,
    d.total_txns,
    d.unique_customers_served,
    round(d.cash_out_amount / nullif(d.cash_in_amount, 0), 2) as cash_out_to_in_ratio,
    coalesce(i.imbalance_severity, 'none') as imbalance_flag
from daily_txns d
join {{ ref('stg_agents') }} ag using (agent_id)
left join imbalance i using (agent_id, txn_date)
