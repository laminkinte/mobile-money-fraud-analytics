-- FRAUD ALERT SUMMARY
-- Collapses fraud_alerts down to one row per transaction, with the number
-- of distinct rules tripped and the highest severity seen. A transaction
-- tripping multiple independent rules is a much stronger signal — this is
-- what the analyst review queue should be sorted by.

select
    transaction_id,
    customer_id,
    txn_timestamp,
    txn_type,
    amount,
    region,
    kyc_tier,
    count(distinct fraud_pattern)                              as rules_tripped,
    string_agg(distinct fraud_pattern, ', ')                   as fraud_patterns,
    max(case severity when 'high' then 2 when 'medium' then 1 else 0 end) as max_severity_rank,
    case max(case severity when 'high' then 2 when 'medium' then 1 else 0 end)
        when 2 then 'high'
        when 1 then 'medium'
        else 'low'
    end                                                          as max_severity,
    min(review_status)                                          as review_status
from {{ ref('fraud_alerts') }}
group by transaction_id, customer_id, txn_timestamp, txn_type, amount, region, kyc_tier
order by rules_tripped desc, max_severity_rank desc
