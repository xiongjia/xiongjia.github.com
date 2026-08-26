-- Product dimension: master data + sales stats (units sold / avg sold price).
select
    p.product_id,
    p.name,
    p.category,
    p.list_price,
    round(avg(oi.unit_price), 2)     as avg_sold_price,
    coalesce(sum(oi.quantity), 0)    as units_sold
from {{ ref('stg_products') }} p
left join {{ ref('stg_order_items') }} oi
  on oi.product_id = p.product_id
group by p.product_id, p.name, p.category, p.list_price