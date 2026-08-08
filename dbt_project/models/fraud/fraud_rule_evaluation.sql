-- FRAUD RULE EVALUATION
-- Scores rule-based detection against eval.fraud_ground_truth (the labels
-- withheld from the "production" transactions feed). This is what you'd
-- show in a portfolio write-up or interview: "here's my detection recall
-- and false positive rate, per rule and overall."
--
-- NOTE: eval.fraud_ground_truth only exists because this is a synthetic
-- benchmark dataset. In production this table would not exist — this
-- model is for demonstrating/tuning the rules, not for the live pipeline.

with flagged as (
    select distinct transaction_id
    from {{ ref('fraud_alert_summary') }}
),

truth as (
    select transaction_id, is_fraud, fraud_pattern as true_pattern
    from {{ source('eval', 'fraud_ground_truth') }}
),

scored as (
    select
        t.transaction_id,
        t.is_fraud,
        t.true_pattern,
        case when f.transaction_id is not null then true else false end as was_flagged
    from truth t
    left join flagged f using (transaction_id)
)

select
    count(*)                                                            as total_transactions,
    sum(case when is_fraud then 1 else 0 end)                           as total_actual_fraud,
    sum(case when was_flagged then 1 else 0 end)                        as total_flagged,
    sum(case when is_fraud and was_flagged then 1 else 0 end)           as true_positives,
    sum(case when not is_fraud and was_flagged then 1 else 0 end)       as false_positives,
    sum(case when is_fraud and not was_flagged then 1 else 0 end)       as false_negatives,
    round(safe_divide(
        sum(case when is_fraud and was_flagged then 1 else 0 end),
        sum(case when is_fraud then 1 else 0 end)
    ), 4)                                                                as recall,
    round(safe_divide(
        sum(case when is_fraud and was_flagged then 1 else 0 end),
        sum(case when was_flagged then 1 else 0 end)
    ), 4)                                                                as precision
from scored
