---
icon: material/folder-open
hide:
  - tags
tags: [tech]
---

# 📦 Collection

Tools + Frameworks + others



### C / C++

- [boost](tech/dev/boost.md) - boost 日常使用
- [abseil](https://abseil.io/){:target="\_blank"} - [abseil-github](https://github.com/abseil/abseil-cpp); [abseil-blog](https://abseil.io/blog/)

### Java

- [jodd](https://github.com/oblac/jodd){:target="\_blank"} - 各种工具库的独立实现，不一定最好但都比较小巧。
- [byte-buddy](https://github.com/raphw/byte-buddy){:target="\_blank"} - Runtime code generation

### golang

- [zap](https://github.com/uber-go/zap){:target="\_blank"} - log library 特点是速度快，占用内存少
- [viper](https://github.com/spf13/viper){:target="\_blank"} - configuration solution for Go applications
- [gorm](https://github.com/go-gorm/gorm){:target="\_blank"} - ORM library for Golang
- [gin](https://github.com/gin-gonic/gin){:target="\_blank"} - HTTP web framework
- [httprouter](https://github.com/julienschmidt/httprouter){:target="\_blank"} - HTTP request router
- [Standard Go Project Layout](https://github.com/golang-standards/project-layout/){:target="\_blank"} - Standard Go Project Layout
- [go-prompt](https://github.com/c-bata/go-prompt){:target="\_blank"} - python-prompt-toolkit 的 golang 平替。tui library
- [bubbletea](https://github.com/charmbracelet/bubbletea){:target="\_blank"} - golang tui library
- [cobra](https://github.com/spf13/cobra){:target="\_blank"} - command 解析库。类似 hugao 的命令行解析就用了这个实现。

### Frontend

- [prettier](https://prettier.io/){:target="\_blank"} - 统一代码风格。提供命令行操作和各种编辑器的 plugins (比如：vim, vscode)，在编辑器里按保存时会自动整理代码，避免开发时风格的不统一。[prettier Github](https://github.com/prettier/prettier){:target="\_blank"}
- [lint-staged](https://github.com/okonet/lint-staged){:target="\_blank"} - 通过 npm 生态安装。在 git commit 时触发，一般用于执行 lint 命令。（也可以做其他)
- [Mostly adequate guide to FP (in javascript)](https://github.com/MostlyAdequate/mostly-adequate-guide){:target="\_blank"} - 通用 FP 教程
- [storybook.js](https://storybook.js.org/){:target="\_blank"} - UI compoents 文档生成工具

### React

- [mui](https://github.com/mui/material-ui){:target="\_blank"} - Public UI Components
- [awesome mui (nadunindunil)](https://github.com/nadunindunil/awesome-material-ui){:target="\_blank"} - awesome 系
- [preact](https://github.com/preactjs/preact){:target="\_blank"} - 精简版 react 。至少有 2 个好处，.js 文件的大小更小；源代码更加易于理解。坏处目前觉得是以后可能跟不上 react 生态圈。
- [awesome preact](https://github.com/preactjs/awesome-preact){:target="\_blank"}
- [emotion-js](https://github.com/emotion-js/emotion){:target="\_blank"} - 方便在 JS, TS 中添加 components 的 css
- [React Pro Sidebar](https://github.com/azouaoui-med/react-pro-sidebar){:target="\_blank"} - sidebar component
- [jotai](https://github.com/pmndrs/jotai){:target="\_blank"} - state management

### sample projects

- [React Board](https://github.com/aditya0929/reactBoard){:target="\_blank"} - Dash board sample. [Demo APP](https://advance-dash.netlify.app/){:target="\_blank"}

### DEV Tools / Libraries

- [playwright](https://github.com/microsoft/playwright){:target="\_blank"} - UI Automation testing framework ( MS 维护，文档全面。提供 VS Extension 帮助脚本开发)
- [ddosify](https://github.com/ddosify/ddosify){:target="\_blank"} - Stress / Loading tests framework
- [xxHash](https://cyan4973.github.io/xxHash/){:target="\_blank"} - 比 MD5 和 SHA1 快出很多的 hash 实现。用于计算内测数据的 hash 比较合适，用来做文件的摘要意义不大，因为瓶颈一般做 disk I/O 上。 [xxHash Github](https://github.com/Cyan4973/xxHash){:target="\_blank"}；[xxHash Golang 实现](https://github.com/cespare/xxhash/){:target="\_blank"}

## 🐼 DB

### Key-Value Database

- [Dragon Fly DB](https://dragonflydb.io/){:target="\_blank"} - 类 redis ，看统计比 redis 快，占内存少

### Time series database

- [GrepTimeDb](https://github.com/GreptimeTeam/greptimedb){:target="\_blank"} - rust 实现的 TS DB

### SQLite

- [SQLite](https://www.sqlite.org/){:target="\_blank"} ; [SQLite Docs](https://www.sqlite.org/docs.html){:target="\_blank"}
- [SQLite Github mirror](https://github.com/sqlite/sqlite){:target="\_blank"}
- [SQLite 源代码解析](https://huili.github.io/sqlite/sqliteintro.html){:target="\_blank"}
- [rqlite](https://github.com/rqlite/rqlite){:target="\_blank"} - Golang 封装 raft + SQLite 实现的分布式数据库

### [PostgreSQL](https://www.postgresql.org/){:target="\_blank"} 系列

- [patroni](https://github.com/zalando/patroni){:target="\_blank"} - python 实现 PG 集群配置工具 (依赖 ETCD )

### DB tools

- [dbeaver](https://dbeaver.io){:target="\_blank"} - 支持各种数据库的管理工具。基于 Java, JDBC 用 Eclipse 改的界面。社区版本免费。

## 🐥 distributed systems

### Services discovery

- [zookeeper](https://github.com/apache/zookeeper){:target="\_blank"}
- [etcd](https://github.com/etcd-io/etcd){:target="\_blank"}
- [nacos](https://github.com/alibaba/nacos){:target="\_blank"} - 安全漏洞多，最好只内网用用

## 🛠️ Dev-Ops

- [ntfy](https://ntfy.sh/){:target="\_blank"} - 通知系统
- [gotify](https://gotify.net/){:target="\_blank"} - 通知系统
- 分发部署系统: saltstack, ansible, puppet, chef, rudder, fabric, Terraform

## ☎️ RPC

- [ZMQ](https://zeromq.org/){:target="\_blank"} - [zmq-github](https://github.com/zeromq) 不需要额外部署 (Zero)
- [d-bus](https://github.com/freedesktop/dbus){:target="\_blank"} - IPC 通信
- [gRPC](https://grpc.io/){:target="\_blank"} - HTTP2 + protobuf
- [RSocket](https://rsocket.io/){:target="\_blank"} - 有浏览器支持
- [thrift](https://thrift.apache.org/){:target="\_blank"}
- [avro](https://avro.apache.org/){:target="\_blank"}

## 🍎 Serialization Frameworks

- [protobuf](tech/dev/protobuf.md) - 速度比较快
- [msgpack](https://msgpack.org/){:target="\_blank"} - 和 JSON 差不多。压缩版 JSON
- [pickle](https://docs.python.org/3/library/pickle.html){:target="\_blank"} - Python 自带。二进制序列号格式
- [cbor](https://cbor.io/){:target="\_blank"} - binary object, 能用的库不多
- [bson](https://bsonspec.org/){:target="\_blank"} - binary json , MongoDB 里用的就是 bson
- [Json Lines](https://jsonlines.org/){:target="\_blank"} - JSON 改良
- [thrift](https://thrift.apache.org/){:target="\_blank"} - RPC 库里用的
- [FlatBuffers](https://google.github.io/flatbuffers/){:target="\_blank"} - 为游戏开发设计。（应该是不做数据压缩，解析更快，但比较耗内存和带宽)
- [parquet](https://parquet.apache.org/){:target="\_blank"} - Columnar storage for Hadoop workloads. (Binary)
- [srsly](https://github.com/explosion/srsly){:target="\_blank"} - python 的库
- [Java Object Serialization](https://docs.oracle.com/javase/8/docs/technotes/guides/serialization/index.html){:target="\_blank"} - JDK / JRE 自带
- [ion](https://amzn.github.io/ion-docs/){:target="\_blank"} - Amazone 开发
- [npy](https://numpy.org/devdocs/reference/generated/numpy.lib.format.html){:target="\_blank"} - Python NumPy 自带
- [Json LD](https://json-ld.org/){:target="\_blank"} - 改良版 JSON ，适合重复数据多
- [gobs](https://pkg.go.dev/encoding/gob){:target="\_blank"} - golang 自带
- Boost.Serialization - Boost 的一个模块，只适合 c++ [Boost.Serialization 1.8](https://www.boost.org/doc/libs/1_80_0/libs/serialization/doc/index.html){:target="\_blank"}
- Others: Yaml; Toml; xml; Plist (MacOS 里用的那个)

## 📺 Entertainment

### media system

- [jellyfin](https://jellyfin.org/){:target="\_blank"} - .NET 实现的流管理
- [emby](https://emby.media/){:target="\_blank"} - .NET 实现的流管理
- [plex](https://www.plex.tv/){:target="\_blank"}
- [TMM](https://www.tinymediamanager.org/){:target="\_blank"}
- [kodi](https://kodi.tv/){:target="\_blank"}; [kodi-github](https://github.com/xbmc){:target="\_blank"}

### trackers / radarr

- [Sonarr](https://github.com/Sonarr/Sonarr){:target="\_blank"} -  自动下载找源 (电视剧管理与自动下载)
- [Radarr](https://github.com/Radarr/Radarr){:target="\_blank"} - sonarr 复刻 (电影管理与自动下载)
- [Jackett](https://github.com/Jackett/Jackett){:target="\_blank"} - 找源工具

### Movie DB

- [imdb](https://www.imdb.com/){:target="\_blank"} - 缺少开放接口
- [omdbapi](https://www.omdbapi.com/){:target="\_blank"} - 基本不维护
- [tmdb](https://www.themoviedb.org/){:target="\_blank"} - 目前看最开放

## 🤖 Tools

- [trickle](https://github.com/mariusae/trickle){:target="\_blank"} - 带宽限速
- [mitmproxy](https://mitmproxy.org/){:target="\_blank"} - 解析 http / https 协议用的反向工程工具
- [ttar](https://github.com/ideaship/ttar){:target="\_blank"} - 文本文件打包工具
- [flameshot](https://github.com/flameshot-org/flameshot){:target="\_blank"} - 截屏工具
- [go-guerrilla](https://github.com/flashmob/go-guerrilla){:target="\_blank"} - Mini SMTP server written in golang
- [coreutils rust](https://github.com/uutils/coreutils){:target="\_blank"} - unix core utils 的 rust 实现版本
- [podman](https://podman.io/){:target="\_blank"} - daemonless container engine
- [ledger-cli](https://ledger-cli.org/){:target="\_blank"} - 复式记账工具。可以和 Emacs, Obsidian 等工具组合使用
- [Beancount](https://beancount.github.io/){:target="\_blank"} - 类似 ledger 。使用入门更方便可以结合 [Fava](https://github.com/beancount/fava){:target="\_blank"} 的 web 界面使用。

## 👀 Monitoring tool

### Prometheus 系

- [node_exporter](https://github.com/prometheus/node_exporter){:target="\_blank"} - Exporter for machine metrics
- [alertmanager](https://github.com/prometheus/alertmanager){:target="\_blank"} - Prometheus Alertmanager
- [ethtool golang](github.com/safchain/ethtool){:target="\_blank"} - ethtool 的 golang 实现 Prometheus 内部调用
- [proc fs](https://github.com/prometheus/procfs){:target="\_blank"} - golang 实现的 proc fs 解析工具。 Prometheus 内部组件

### Application Performance Monitoring

- [skywalking](https://github.com/apache/skywalking){:target="\_blank"}
- [pinpoint](https://github.com/pinpoint-apm/pinpoint){:target="\_blank"}

### Misc

- [sysstat](https://github.com/sysstat/sysstat){:target="\_blank"} - Performance monitoring tools for Linux
- [Server Status Rust](https://github.com/zdz/ServerStatus-Rust){:target="\_blank"} - Rust 实现的服务器监测
- [uptime kuma](https://github.com/louislam/uptime-kuma){:target="\_blank"} - A fancy self-hosted monitoring tool
- [vnStat](tech/oss/vnstat.md) - a network traffic monitor for Linux and BSD
- [btop](https://github.com/aristocratos/bpytop){:target="\_blank"} - 改良版本 top
- [netdata](https://github.com/netdata/netdata){:target="\_blank"} - Real-time performance monitoring 是 c / c++ 实现，也支持自己写 Collector 扩展。(比较适合做单机的时时检查用)
- [nmon](https://nmon.sourceforge.net/pmwiki.php) - 用 cli 也支持 csv 导出后的分析。适合单机检查、分析具体问题。

## 🐵 github

### github tools

- [Open Source Software Insight](https://ossinsight.io/){:target="\_blank"} - github 的一些统计
- [giscus](https://giscus.app/){:target="\_blank"} - 基于 github discussions 做的 BLOG 留言系统
- [utteranc](https://utteranc.es/){:target="\_blank"} - 基于 github issue 做的 BLOG 留言系统

### ENU

- [awesome english book](https://github.com/hehonghui/awesome-english-ebooks){:target="\_blank"}

## 🎮 Games

- [NS Emulator](https://github.com/Ryujinx/Ryujinx){:target="\_blank"} - .NET 实现的 NS 模拟器。（已经停止维护了）

## 🦚 OS distribution

- [AlmaLinux](https://almalinux.org/){:target="\_blank"} - CentOS 替代
- [clear os](https://www.clearos.com/){:target="\_blank"} - 类似 Redhat, CentOS 不过适合 NAS 管理，有一些远程管理工具。

## Windows

- [scoop](https://scoop.sh/){:target="\_blank"} - Windows package management

## 📚 Tutorials

- [web.dev/learn](https://web.dev/learn/){:target="\_blank"} - 基础 html 教程
- [TypeScript Challenges](https://github.com/type-challenges/type-challenges){:target="\_blank"} - TypeScript 练习
- [CS DIY](https://csdiy.wiki/){:target="\_blank"} - Computer science 自学目录
- [µGo 语言实现(从头开发一个迷你 Go 语言编译器)](https://github.com/wa-lang/ugo-compiler-book){:target="\_blank"} - go 编译器学习
- [Go 语言定制指南](https://github.com/chai2010/go-ast-book){:target="\_blank"} - Go 语法树入门




