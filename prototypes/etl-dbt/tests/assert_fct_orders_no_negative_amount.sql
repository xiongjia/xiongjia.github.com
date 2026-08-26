-- Singular test: no order should carry a negative gross amount in the fact table.
select
    order_id,
    gross_amount
from {{ ref('fct_orders') }}
where gross_amount < 0