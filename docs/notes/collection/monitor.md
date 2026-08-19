---
icon: material/chart-bell-curve
hide:
  - tags
---

# :material-chart-bell-curve: Monitor

## TSDB & Metrics Stack

- [Prometheus](https://github.com/prometheus/prometheus) - 云原生指标监控事实标准：Pull 模式、PromQL、生态极丰富、K8s 原生
- [VictoriaMetrics](https://github.com/VictoriaMetrics/VictoriaMetrics) - 高性能 Prometheus 兼容 TSDB：单节点/集群、高压缩比、低成本替代、支持 remote_write
- [Thanos](https://github.com/thanos-io/thanos) - Prometheus 长期存储 & 全局视图：对象存储后端、全局查询、降采样
- [Mimir](https://github.com/grafana/mimir) - Grafana Labs 的 Prometheus 兼容方案：水平扩展、多租户、Grafana Cloud 核心
- [InfluxDB](https://github.com/influxdata/influxdb) - 通用时序数据库：早期流行、Flux 查询语言、有开源/商业版
- [TimescaleDB](https://github.com/timescale/timescaledb) - 基于 PostgreSQL 的时序扩展：SQL 友好、兼容 PG 生态
- [Cortex](https://github.com/cortexproject/cortex) - Prometheus 水平扩展方案（Mimir 前身）：多租户、长期存储，现由 Mimir 接替
- [Graphite](https://github.com/graphite-project/graphite-web) - 经典 TSDB：Whisper 存储、Carbon 采集、Grafana 原生支持
- [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector) - 统一采集代理：接收多种协议、转换、导出到任意后端

## Prometheus Ecosystem

- [node_exporter](https://github.com/prometheus/node_exporter) - Machine metrics exporter
- [alertmanager](https://github.com/prometheus/alertmanager) - Alerting
- [ethtool golang](https://github.com/safchain/ethtool) - ethtool Go 实现
- [proc fs](https://github.com/prometheus/procfs) - proc fs 解析工具

## eBPF Observability

- [Grafana Beyla](https://github.com/grafana/beyla) - eBPF 自动 APM：无侵入、自动发现 HTTP/gRPC/Redis 等
- [Pixie (New Relic)](https://github.com/pixie-io/pixie) - K8s 实时调试：eBPF 采集、无需插码、脚本化查询
- [Falco](https://github.com/falcosecurity/falco) - 云原生安全监控：eBPF 检测异常系统调用、CNCF 毕业
- [Cilium + Hubble](https://github.com/cilium/cilium) - K8s 网络可观测：eBPF 网络策略 + 流量可视化
- [Tetragon (Cilium)](https://github.com/cilium/tetragon) - eBPF 安全可观测：进程执行、文件访问、网络连接追踪

## APM

- [skywalking](https://github.com/apache/skywalking)
- [pinpoint](https://github.com/pinpoint-apm/pinpoint)

## System Monitoring

- [sysstat](https://github.com/sysstat/sysstat) - Linux performance monitoring
- [Server Status Rust](https://github.com/zdz/ServerStatus-Rust) - Rust 服务器监测
- [uptime kuma](https://github.com/louislam/uptime-kuma) - Self-hosted monitoring
- [btop](https://github.com/aristocratos/bpytop) - 改良版 top
- [netdata](https://github.com/netdata/netdata) - Real-time performance monitoring
- [nmon](https://nmon.sourceforge.net/pmwiki.php) - CLI 监控 + CSV 导出分析
- [monoscope](https://github.com/monoscope-tech/monoscope) - 监控工具
