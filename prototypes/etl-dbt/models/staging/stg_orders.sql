-- Clean order headers: keep only valid orders (drop cancelled; relax if needed).
select
    id                              as order_id,
    customer_id,
    order_date,
    status,
    updated_at
from {{ source('raw', 'orders') }}
where status in ('placed', 'completed')