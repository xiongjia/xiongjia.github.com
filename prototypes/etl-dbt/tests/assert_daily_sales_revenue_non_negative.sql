-- Singular test: daily revenue must never be negative.
select
    order_date,
    net_revenue
from {{ ref('daily_sales') }}
where net_revenue < 0