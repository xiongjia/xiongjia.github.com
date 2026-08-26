-- Customer dimension: master data + lifetime behavior (order count / GMV).
select
    c.customer_id,
    c.name,
    c.email,
    c.country,
    c.created_date,
    coalesce(agg.order_count, 0)    as lifetime_orders,
    coalesce(agg.lifetime_gmv, 0)   as lifetime_gmv
from {{ ref('stg_customers') }} c
left join (
    select
        customer_id,
        count(*)                     as order_count,
        round(sum(net_amount), 2)    as lifetime_gmv
    from {{ ref('fct_orders') }}
    group by customer_id
) agg on agg.customer_id = c.customer_id