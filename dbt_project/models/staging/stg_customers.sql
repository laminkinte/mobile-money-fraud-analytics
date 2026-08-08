-- Light cleaning/typing pass over raw.customers. One row per customer.

select
    customer_id,
    kyc_tier,
    trim(home_region)      as home_region,
    registration_date,
    date_diff(current_date, registration_date, day) as account_age_days
from {{ source('raw', 'customers') }}
