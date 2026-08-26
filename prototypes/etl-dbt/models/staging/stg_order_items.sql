-- Standardize order items; compute the line total (with discount) once here
-- so downstream models can reuse it.
select
    id                              as item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    discount,
    round(unit_price * quantity * (1 - discount), 2) as line_total
from {{ source('raw', 'order_items') }}