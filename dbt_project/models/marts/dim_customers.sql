select
    customer_id,
    kyc_tier,
    home_region,
    registration_date,
    account_age_days
from {{ ref('stg_customers') }}
