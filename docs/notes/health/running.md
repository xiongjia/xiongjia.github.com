---
icon: fontawesome/solid/person-running
hide:
  - tags
---

# 🏃 Running Track

## 🕓 数据同步

{{ running_synced_at() }}

______________________________________________________________________

## 🔥 跑步记录

{{ running_calendar_heatmap() }}

______________________________________________________________________

## 🕐 最近活动

{{ running_splits_note() }}

{{ running_recent() }}

### 🗺️ 路线

{{ running_recent_routes(max_routes=10) }}

______________________________________________________________________

<details><summary>📅 年度统计</summary>

{{ running_year_table() }}

</details>

______________________________________________________________________

<details><summary>📈 月度里程与心率趋势</summary>

{{ running_monthly_chart() }}

</details>

______________________________________________________________________

{{ running_all() }}
