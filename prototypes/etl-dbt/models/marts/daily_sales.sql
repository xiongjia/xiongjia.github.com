-- Daily sales rollup -- the INCREMENTAL model (the key demo).
--
-- Three incremental ingredients:
--   1. materialized = 'incremental'           tells dbt this is an incremental model
--   2. incremental_strategy = 'delete+insert' deletes rows by unique_key then inserts
--      new ones (supports re-processing / backfilling a specific day)
--   3. is_incremental() block                 skipped on the first full build; on later
--      runs only data after the last processed day is selected
--
-- delete+insert is the recommended strategy on DuckDB: no complex merge syntax,
-- and unique_key gives you idempotent re-runs for a given day.
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='order_date',
) }}

select
    o.order_date,
    count(distinct o.order_id)              as order_count,
    count(oi.item_id)                       as item_count,
    round(coalesce(sum(oi.unit_price * oi.quantity), 0), 2) as gross_revenue,
    round(coalesce(sum(oi.line_total), 0), 2)                as net_revenue
from {{ ref('stg_orders') }} o
left join {{ ref('stg_order_items') }} oi
  on oi.order_id = o.order_id
{% if is_incremental() %}
-- Incremental: only process data after the last date already in the table.
where o.order_date > (select max(order_date) from {{ this }})
{% endif %}
group by o.order_date