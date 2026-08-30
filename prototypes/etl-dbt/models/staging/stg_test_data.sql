-- staging: read the raw seed table, clean and transform.
-- {{ ref('test_data') }} links to the test_data table created by dbt seed.
-- Status contract: only `valid` rows pass; `cancelled` must never leak here.
-- Cross-checked by tests/assert_stg_test_data_no_cancelled.sql.
select
    order_id,
    order_date,
    customer_name,
    product,
    category,
    qty,
    unit_price,
    round(qty * unit_price, 2) as line_total,  -- computed column added here
    status
from {{ ref('test_data') }}
where status = 'valid'  -- keep only valid orders, drop cancelled
