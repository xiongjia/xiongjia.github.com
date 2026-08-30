-- Singular test: line_total must equal qty * unit_price.
-- Any row where the recomputation mismatches = FAIL.
-- Note: this guards the model FORMULA (fails if stg_test_data.sql's
-- line_total expression changes). All seed prices have 2 decimals, so with
-- the fixed data it cannot catch a wrong formula on the seed itself --
-- add a 3-decimal price row if you want that extra sensitivity.
select order_id, qty, unit_price, line_total
from {{ ref('stg_test_data') }}
where round(qty * unit_price, 2) <> line_total
