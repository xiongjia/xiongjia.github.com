-- Order fact table: one row per order, line amounts rolled up from order items.
-- gross = list prices before discount; net = after discount (what was collected).
select
    o.order_id,
    o.customer_id,
    o.order_date,
    o.status,
    count(oi.item_id)                        as item_count,
    round(coalesce(sum(oi.unit_price * oi.quantity), 0), 2) as gross_amount,
    round(coalesce(sum(oi.line_total), 0), 2)                as net_amount
from {{ ref('stg_orders') }} o
join {{ ref('stg_order_items') }} oi
  on oi.order_id = o.order_id
group by o.order_id, o.customer_id, o.order_date, o.status