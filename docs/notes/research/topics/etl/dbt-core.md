---
hide:
  - navigation
title: dbt-core 本地 ETL 实战（DuckDB）
tags:
  - research
  - tech
  - etl
  - dbt
  - duckdb
  - incremental
categories:
  - dev
---

# dbt-core 本地 ETL 实战（DuckDB）

> 对应的可运行原型：`prototypes/etl-dbt/`（随仓库提交，见 [Prototypes 列表](../../../prototypes.md)）。
> 本文记录「为什么这么配、怎么跑、增量是怎么回事」，配合原型代码阅读。

## 1. 目标与总体思路

需求拆解（对应本地开发草稿）：

1. **目前先只增加一个 dbt-core 的使用** —— 工具链先选 dbt-core，其余（Airflow 调度、
   容器 PG、CDC 等）留作后续。
1. **找一个本地测试的办法** —— 选 **DuckDB**（dbt-duckdb 适配器）。理由：
   - 零服务：没有 PostgreSQL 容器、没有端口/权限问题，一个 `.duckdb` 文件就是数据库；
   - 和 dbt 原生集成：适配器开箱支持 `view / table / incremental` 三种物化，增量策略
     `append / delete+insert / merge` 都可用；
   - 文件即数据：适合建模实验、CI 里快速跑、以及把结果当文件交付。
1. **生成模拟原始数据** —— 见原型 `scripts/generate_mock_data.py`（电商场景：
   customers / products / orders / order_items，日期从 2026-06-01 起，固定 seed 可复现）。
1. **配置转换过程** —— dbt 分层：`staging`（清洗/标准化，视图）→ `marts`
   （维度/事实/汇总，落表）。源表通过 `attach` 挂到 dbt 里，模拟独立的「源数据库」。
1. **生成目标数据** —— 结果写到 `data/analytics.duckdb`（目标库），与 `raw.duckdb` 分离。
1. **注意增量如何配置** —— 核心演示：`daily_sales` 增量模型，见下文 §4。

## 2. 安装与环境

原型工程随本仓库（xiongjia.github.com）提交，放在仓库根的 `prototypes/` 目录下
（实验性 mini-project 集散地，见 [Prototypes 列表](../../../prototypes.md)）；
本实验对应子目录 `prototypes/etl-dbt/`。以下命令都从仓库根执行：

```bash
cd prototypes/etl-dbt
uv sync    # 安装 dbt-core + dbt-duckdb 到 .venv
uv run dbt --version
```

验证两个版本都出现：

```
Core:   - installed: 1.12.3
Plugins:
  - duckdb: 1.11.0
```

> 安装提示：`dbt-core 1.12` 会拉一个从 GitHub Releases 下载 wheel 的依赖
> （`dbt-core-experimental-parser`），首次安装可能较慢；失败时原样重跑
> `uv sync` 即可。

## 3. 项目结构（转换过程是怎么配置的）

```
etl-dbt/
├── dbt_project.yml          # 项目名/路径/默认物化（staging=view, marts=table, daily_sales=incremental）
├── profiles/profiles.yml    # DuckDB profile：path=data/analytics.duckdb + attach raw.duckdb
├── scripts/generate_mock_data.py   # 生成/追加模拟原始数据
├── models/
│   ├── sources.yml          # 源表声明（database=raw ← attach 的别名, schema=main）
│   ├── staging/             # stg_* 视图：改名、类型转换、剔除 cancelled 订单
│   └── marts/               # fct_orders / dim_customers / dim_products / daily_sales 表
├── tests/                   # singular test（负金额、非负营收等）
└── data/                    # gitignored：raw.duckdb（源）与 analytics.duckdb（目标）
```

关键配置点：

- **分层物化**在 `dbt_project.yml` 的 `models.etl_dbt.*` 下按目录统一声明：
  staging 全部 `view`（不落地，省空间、反映源库实时变化），marts 默认 `table`，
  `daily_sales` 单独覆盖为 `incremental`。
- **源库 attach**：`profiles/profiles.yml` 里 `attach: [{path: data/raw.duckdb, alias: raw}]`，
  `sources.yml` 里 `database: raw`。这样模型里写 `source('raw', 'orders')`，
  dbt 编译后就是 `raw.main.orders` —— 源和目标物理上分两个文件，贴近真实 ETL 的
  「源库 → 目标库」隔离。
- 模型间依赖用 `{{ ref(...) }}`，dbt 自动编排执行顺序：staging 先于 marts，
  `fct_orders` 先于引用它的 `dim_customers`。

## 4. 增量配置（重点）

`models/marts/daily_sales.sql` 是增量模型的完整例子：

```sql
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='order_date',
) }}

select
    o.order_date,
    count(distinct o.order_id)              as order_count,
    ...
from {{ ref('stg_orders') }} o
left join {{ ref('stg_order_items') }} oi on oi.order_id = o.order_id
{% if is_incremental() %}
where o.order_date > (select max(order_date) from {{ this }})
{% endif %}
group by o.order_date
```

三个要素缺一不可：

1. `materialized='incremental'` —— 告诉 dbt 这是增量模型：首次运行全量建表，
   之后每次运行尽量只处理新数据、不重建整表。

1. `incremental_strategy='delete+insert'` —— 增量具体怎么落。流程：先把本次计算的
   新数据放进临时表，按 `unique_key` delete 表里已存在的对应行，再 insert 全部新行。
   好处：**幂等**、支持「回刷/修正某天」（同一 unique_key 重复跑不会积重复行）。
   对比：`append` 最快但会积重复；`merge` 需要唯一键合并语法，DuckDB 上
   delete+insert 是推荐策略。

1. `is_incremental()` 条件 —— 决定每次「增量只取哪些数据」。编译后对应 SQL：

   ```sql
   where o.order_date > (select max(order_date) from daily_sales)
   ```

   即只处理目标表里最大日期之后的新数据。这里按 `order_date` 分界是「以天数做
   增量窗口」的最简做法；生产上常换成 `updated_at` 时间戳做 CDC 型增量。

### 跑增量演练

```bash
# 全量（30 天）
uv run python scripts/generate_mock_data.py
DBT_PROFILES_DIR=profiles uv run dbt build            # 首次：全量建表，daily_sales=30 行

# 追加 2 天新数据（2026-07-01 ~ 07-02）
uv run python scripts/generate_mock_data.py --append-days 2

# 只重建增量模型
DBT_PROFILES_DIR=profiles uv run dbt build --select daily_sales
# daily_sales: 30 行 → 32 行，只新增了两天
```

验证结果表（`data/analytics.duckdb`）：

| 模型          | 全量后            | 增量后             | 说明                       |
| ------------- | ----------------- | ------------------ | -------------------------- |
| daily_sales   | 30 行（6/1–6/30） | 32 行（+7/1、7/2） | 增量只处理新日期           |
| fct_orders    | 873 行            | （未重建）         | 订单事实，已剔除 cancelled |
| dim_customers | 200 行            | —                  | 客户维度 + lifetime GMV    |
| dim_products  | 40 行             | —                  | 商品维度 + 销量            |

> 注意：增量只重建 `daily_sales` 时，`fct_orders` / `dim_*` 不会自动更新（它们没有
> 依赖新数据）。生产上通常把「由新数据驱动、需要更新的下游」也放进同一个
> incremental 批次（如 `dbt build --select daily_sales+` 带下游），或给它们配置
> 增量/按分区重建。

## 5. 测试

- **Generic tests**（`models/*/schema.yml`）：`unique`、`not_null` 挂在各列上；
- **Singular tests**（`tests/`）：`assert_fct_orders_no_negative_amount`、
  `assert_daily_sales_revenue_non_negative` 直接写 SQL 断言业务规则。
- 跑 `dbt build` 时模型与测试一起执行（PASS/FAIL 一目了然），也可以只跑
  `dbt test`。

## 6. 遇到的经验 / 坑

- **DuckDB 1.5 的 catalog 命名**：本地文件 `raw.duckdb` 的 catalog 名 = 文件名
  （`raw`），默认 schema 仍是 `main`。所以全限定是 `raw.main.<table>`；
  写 `raw.<table>` 会被 DuckDB 报「ambiguous catalog or schema」。dbt 侧
  `sources.yml` 用 `database: raw, schema: main`，编译后正好生成 `raw.main.*`。
- **脚本里不要建重复 schema**：DuckDB 1.5 的 `duckdb_catalogs()` 等内省表函数
  已改名，排查 catalog 名直接用 `SELECT current_database(), current_schema()`。
- **Python 3.13 与 dbt-core 1.12.3** 组合正常；prototype 用 `uv python pin 3.13` 固定。
- 数据生成器用固定 seed（`--seed 42`），保证 mock 数据可复现、可对比。
- 追加模式必须延续现有 `max(id)`，否则新增行主键与旧数据重复：mock 表没有
  主键约束不会报错，但 `unique` 测试会在下一次全量 `dbt build` 时失败，且破坏
  「id 即真实业务键」的假设（脚本已自动从 `max(id)+1` 继续）。

## 7. 后续方向

- 容器 PostgreSQL 作为本地源库（`dbt-postgres` + docker compose），对比数据库源；
- 用 `dbt-external-tables` / parquet 外部表做「文件即源」，配合 `bucket-sync` 的数据资产；
- 增量窗口升级为 CDC 风格（`updated_at` + 删除标记），并用 `dbt build --select daily_sales+`
  串联下游重建；
- 接入调度（cron / Airflow / Dagster）与 CI（`dbt build` + `dbt test` 进 GitHub Actions）。
