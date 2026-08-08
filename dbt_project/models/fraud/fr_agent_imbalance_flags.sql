-- RULE 3 — AGENT CASH IMBALANCE (till-tapping)
-- Flags agent-days where cash-out volume far exceeds cash-in volume,
-- beyond what the agent's opening float could plausibly support.
-- Real fintechs run this daily per-agent as a reconciliation check.

{% set imbalance_ratio_threshold = 3.0 %}

with daily as (
    select
        agent_id,
        txn_date,
        sum(case when txn_type = 'cash_in'  then amount else 0 end) as cash_in_amount,
        sum(case when txn_type = 'cash_out' then amount else 0 end) as cash_out_amount,
        count(*) as total_txns
    from {{ ref('stg_transactions') }}
    where agent_id is not null
      and txn_type in ('cash_in', 'cash_out')
    group by agent_id, txn_date
)

select
    agent_id,
    txn_date,
    cash_in_amount,
    cash_out_amount,
    total_txns,
    'agent_imbalance'                     as fraud_pattern,
    round(
        cash_out_amount / nullif(cash_in_amount, 0), 2
    )                                      as rule_metric,
    {{ imbalance_ratio_threshold }}       as rule_threshold,
    case
        when cash_out_amount / nullif(cash_in_amount, 0) >= {{ imbalance_ratio_threshold * 2 }} then 'high'
        when cash_out_amount / nullif(cash_in_amount, 0) >= {{ imbalance_ratio_threshold }}     then 'medium'
    end as severity
from daily
where cash_in_amount = 0
   or (cash_out_amount / nullif(cash_in_amount, 0)) >= {{ imbalance_ratio_threshold }}
