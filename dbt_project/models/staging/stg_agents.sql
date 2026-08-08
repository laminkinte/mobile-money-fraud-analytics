-- Light cleaning/typing pass over raw.agents. One row per agent.

select
    agent_id,
    agent_name,
    trim(region)                as region,
    tier,
    registration_date,
    opening_cash_float,
    date_diff(current_date, registration_date, day) as agent_tenure_days
from {{ source('raw', 'agents') }}
