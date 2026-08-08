select
    agent_id,
    agent_name,
    region,
    tier,
    registration_date,
    opening_cash_float,
    agent_tenure_days
from {{ ref('stg_agents') }}
