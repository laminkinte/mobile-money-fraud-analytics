select
    t.transaction_id,
    t.txn_timestamp,
    t.txn_date,
    t.txn_hour,
    t.txn_type,
    t.amount,
    t.region,
    t.customer_id,
    c.kyc_tier,
    c.account_age_days,
    t.agent_id,
    a.tier                as agent_tier,
    t.counterparty_customer_id
from {{ ref('stg_transactions') }} t
left join {{ ref('stg_customers') }} c using (customer_id)
left join {{ ref('stg_agents') }} a using (agent_id)
