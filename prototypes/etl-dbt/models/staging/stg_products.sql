-- Standardize products: type coercion + null fallback.
select
    id                              as product_id,
    name,
    category,
    coalesce(price, 0)              as list_price,
    created_at::date                as created_date
from {{ source('raw', 'products') }}