# etl-dbt

Minimal dbt call-chain demo: **CSV → seed → staging**.

- Source data is `seeds/test_data.csv`: **10 fixed rows** (orders), no randomness.
- `dbt seed` loads the CSV into a local DuckDB file (`data/analytics.duckdb`) as the
  `test_data` table.
- The single transformation model `stg_test_data` (a view) does the cleaning:
  drop `cancelled` rows, add a computed `line_total` column.
- Fully local: no server, no cloud — just DuckDB files.
- Tooling: `uv run poe fmt` / `poe fmt-check` (sqlfmt for dbt Jinja SQL + mdformat).
- Created 2026-08-26 · status `working` (validated: seed/run/test/build/compile + fmt)

## Layout

```
etl-dbt/
├── pyproject.toml             # uv deps + poe tasks (fmt / fmt-check)
├── uv.lock
├── dbt_project.yml            # model/seed paths, materialization defaults
├── profiles/profiles.yml      # DuckDB profile (writes data/analytics.duckdb)
├── seeds/
│   └── test_data.csv          # source data: 10 fixed order rows
├── models/
│   └── staging/
│       ├── stg_test_data.sql  # the only transformation model (view)
│       └── schema.yml         # column descriptions + generic tests (unique/not_null)
├── tests/
│   ├── assert_stg_test_data_no_cancelled.sql       # singular test: no cancelled in staging
│   └── assert_stg_test_data_line_total_correct.sql # singular test: line_total recomputed correctly
├── target/                   # gitignored dbt artifacts (compiled SQL lives here)
└── data/                     # gitignored duckdb file
```

Data flow:

```
seeds/test_data.csv ── dbt seed ──▶ test_data table (10 raw rows)
                                        │  {{ ref('test_data') }}
                                        ▼
                              stg_test_data view (valid only, + line_total)
                                        │
                                        ▼
                              data/analytics.duckdb
```

## Full command walkthrough

```bash
cd prototypes/etl-dbt
uv sync                                    # install dbt-core + dbt-duckdb + sqlfmt/mdformat/poe

DBT_PROFILES_DIR=profiles uv run dbt seed  # 1. load CSV → test_data table
DBT_PROFILES_DIR=profiles uv run dbt run   # 2. run transformation → stg_test_data view
DBT_PROFILES_DIR=profiles uv run dbt test  # 3. run ALL tests: 5 generic (unique + 4× not_null) + 2 singular
DBT_PROFILES_DIR=profiles uv run dbt test --select assert_stg_test_data_no_cancelled
#    3b. run just ONE test to see a singular test in isolation
#        (singular tests are selected by their bare name — no `test:` prefix)
DBT_PROFILES_DIR=profiles uv run dbt build # 4. one command: seed + run + test
DBT_PROFILES_DIR=profiles uv run dbt compile --select stg_test_data
#    5. inspect the compiled real SQL: target/compiled/etl_dbt/models/staging/stg_test_data.sql
DBT_PROFILES_DIR=profiles uv run dbt compile --select assert_stg_test_data_line_total_correct
#    5b. compile one singular test the same way: target/compiled/etl_dbt/tests/...
uv run poe fmt                               # 6. format SQL (sqlfmt, handles dbt Jinja) + README.md (mdformat)
uv run poe fmt-check                         #    check-only variant (CI-style, no writes)
```

Check the result:

```bash
uv run python -c "import duckdb; c=duckdb.connect('data/analytics.duckdb'); \
print(c.execute('select count(*) from test_data').fetchone()); \
print(c.execute('select order_id, product, line_total from stg_test_data limit 5').fetchall())"
```

Expected: `test_data` has 10 rows, `stg_test_data` has 8 (the 2 `cancelled` rows
dropped), each with `line_total = qty * unit_price`.

> **Troubleshooting** — if you hit "Table with name test_data does not exist":
> some other process is likely holding the DuckDB file (e.g. DBeaver) or the
> database file is stale. Close the external viewer, then rebuild from scratch:
> `rm -f data/analytics.duckdb* && dbt build --profiles-dir profiles`.

## How dbt finds and runs things

### 1. How `dbt seed` finds the CSV

`seed-paths: ["seeds"]` in `dbt_project.yml` tells dbt where to look. dbt scans
that directory for **every `.csv` file**; the filename minus `.csv` becomes the
seed name (`test_data.csv` → seed `test_data`). Each seed becomes a node in the
dbt graph (same as models), and `dbt seed`:

1. reads the header row as column names and infers types — or honors the explicit
   `seeds.etl_dbt.test_data.+column_types` in `dbt_project.yml`
   (`qty: integer`, `unit_price: double`, `order_date: date`)
1. `CREATE TABLE "analytics"."main"."test_data"` + insert each row

No script runs — the CSV itself is the source, loading is the seed. The log line
`OK loaded seed file main.test_data [INSERT 10]` shows it.

### 2. How `dbt run` finds `stg_test_data.sql`

`model-paths: ["models"]` → dbt recursively scans `models/`, and **the filename
is the model name** (`stg_test_data.sql` → model `stg_test_data`).

The `.sql` file is a Jinja template. During compile:

| You write                | dbt compiles to                       | why                                                    |
| ------------------------ | ------------------------------------- | ------------------------------------------------------ |
| `{{ ref('test_data') }}` | `from "analytics"."main"."test_data"` | `ref` resolves the seed's real table name from the DAG |
| `where status = 'valid'` | unchanged                             | plain SQL passes through untouched                     |

Materialization comes from `dbt_project.yml` (`models.etl_dbt.staging.+materialized: view`), so dbt runs `CREATE VIEW` instead of a table. `ref()` also registers the
dependency in the DAG, so `dbt run` always executes seeds before models.

### 3. How `dbt test` judges

Tests declared in `schema.yml` (excerpt — the real file also has `not_null` on
`qty`, `unit_price`, `line_total`, giving 5 generic tests total):

```yaml
- name: order_id
  tests:
    - unique    # → compiled into "find duplicate rows"
    - not_null  # → compiled into "find NULL rows"
```

dbt compiles each declaration into a **violation-finding query** — see
`target/compiled/etl_dbt/models/staging/schema.yml/`:

```sql
-- unique test, compiled:
select order_id as unique_field, count(*) as n_records
from "analytics"."main"."stg_test_data"
where order_id is not null
group by order_id
having count(*) > 1    -- returns rows only when duplicates exist

-- not_null test, compiled:
select order_id
from "analytics"."main"."stg_test_data"
where order_id is null -- returns rows only when NULLs exist
```

**Judgment: execute the query in the real database; 0 rows returned = PASS,
any row returned = FAIL (the violating rows are reported).** Here all 5 generic
test queries (1 × unique + 4 × not_null: order_id, line_total, qty, unit_price)
returned empty; combined with the 2 singular tests below, `dbt test` logs
`PASS=7`.

### 4. Custom checks (singular tests) — cancelled filter & line_total

The generic tests above can only check one column. To check *transformations*,
write **singular tests**: a `.sql` file under `tests/` is a test — you write the
"violation query" yourself, same zero-rows judgment:

```sql
-- tests/assert_stg_test_data_no_cancelled.sql
-- fails if any cancelled row leaked into staging
select order_id
from {{ ref('stg_test_data') }}
where status = 'cancelled'

-- tests/assert_stg_test_data_line_total_correct.sql
-- fails if line_total is not recomputed as qty * unit_price
select order_id, qty, unit_price, line_total
from {{ ref('stg_test_data') }}
where round(qty * unit_price, 2) <> line_total
```

Both are proven to catch violations: run the same queries against the raw
`test_data` table (unfiltered) and they return the 2 cancelled rows; recompute a
wrong `line_total` and all 8 rows are flagged. Log now shows `PASS=7`
(5 generic + 2 singular).

## What is `dbt compile` for?

You write **templates** (Jinja), but the database only executes **pure SQL**.
Compilation is the render step in between: dbt turns `{{ ref('test_data') }}`
into `"analytics"."main"."test_data"`, resolves `{% if %}` branches, applies
config — everything Jinja disappears, leaving executable SQL.

**Every** command that touches models (`run`, `test`, `build`) quietly does this
compile step first, then executes. `dbt compile` is just the command that
**stops after rendering** — no database connection, no writes:

| Command   | Compiles? | Executes? | When to use                                                                       |
| --------- | :-------: | :-------: | --------------------------------------------------------------------------------- |
| `compile` |    ✅     |    ❌     | debug/watch what your template really becomes; review SQL without touching the DB |
| `run`     |    ✅     |    ✅     | actually create the view/table                                                    |
| `test`    |    ✅     |    ✅     | actually run the violation queries                                                |

So `dbt compile --select stg_test_data` answers: *"what SQL would dbt really
send to the database?"* — read `target/compiled/etl_dbt/models/staging/stg_test_data.sql`.
Tests work the same way: their compiled form lives under
`target/compiled/etl_dbt/models/staging/schema.yml/` (generic) and
`target/compiled/etl_dbt/tests/` (singular).

> Fun fact: the table in §2 ("You write → dbt compiles to") is exactly what
> compile shows you — the compiled file is the materialized proof of that table.
> `compile` also refreshes `target/manifest.json`, the full graph snapshot
> (nodes + dependencies) that powers `docs` and state-based CI.

## Key points

- **CSV as source**: dbt seed turns any CSV under `seeds/` into a table directly,
  no import script needed.
- **Explicit seed column types** in `dbt_project.yml` (otherwise seed infers from
  values and may type `order_date` as VARCHAR).
- **Staging as views**: lightweight cleaning, no landing table —
  `+materialized: view` in `dbt_project.yml`.
- `{{ ref('test_data') }}` is the dependency link: compiled to the real table
  name, and `dbt build` runs seeds before models per the DAG.
- Want more data? No code changes — seeds are data-driven: replace the CSV and
  run `dbt seed` again (`--full-refresh` rebuilds).
