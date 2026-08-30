-- Singular test: cancelled orders must not exist in staging.
-- Any row returned = FAIL (a cancelled row leaked into staging).
-- Complements the `status = 'valid'` filter in stg_test_data.sql: if the
-- model filter ever changes, update this test to match.
-- dbt executes this query: 0 rows = PASS, >0 rows = FAIL.
select order_id from {{ ref('stg_test_data') }} where status = 'cancelled'
