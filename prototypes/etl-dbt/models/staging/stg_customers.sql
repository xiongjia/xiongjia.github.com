-- Standardize customers: rename fields, extract date part from created_at.
select
    id                              as customer_id,
    name,
    email,
    country,
    created_at::date                 as created_date
from {{ source('raw', 'customers') }}