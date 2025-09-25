---
icon: material/database-sync-outline
hide:
  - tags
tags: [tech,backend,database,java,golang]
---

# :material-database-sync-outline: Backend


## Collection

日常收集记录（后端 server 开发或者数据库等相关知识工具）

---

### Distributed systems

集群系统相关知识工具

#### Services discovery

- [zookeeper](https://github.com/apache/zookeeper){:target="\_blank"}
- [etcd](https://github.com/etcd-io/etcd){:target="\_blank"}
- [nacos](https://github.com/alibaba/nacos){:target="\_blank"} - 安全漏洞多，最好只内网用用

#### RPC

- [ZMQ](https://zeromq.org/){:target="\_blank"} - [zmq-github](https://github.com/zeromq) 不需要额外部署 (Zero)
- [d-bus](https://github.com/freedesktop/dbus){:target="\_blank"} - IPC 通信
- [gRPC](https://grpc.io/){:target="\_blank"} - HTTP2 + protobuf
- [RSocket](https://rsocket.io/){:target="\_blank"} - 有浏览器支持
- [thrift](https://thrift.apache.org/){:target="\_blank"}
- [avro](https://avro.apache.org/){:target="\_blank"}

#### Serialization Frameworks

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

---

### Monitoring tool

#### Prometheus 系

- [node_exporter](https://github.com/prometheus/node_exporter){:target="\_blank"} - Exporter for machine metrics
- [alertmanager](https://github.com/prometheus/alertmanager){:target="\_blank"} - Prometheus Alertmanager
- [ethtool golang](github.com/safchain/ethtool){:target="\_blank"} - ethtool 的 golang 实现 Prometheus 内部调用
- [proc fs](https://github.com/prometheus/procfs){:target="\_blank"} - golang 实现的 proc fs 解析工具。 Prometheus 内部组件

#### Application Performance Monitoring

- [skywalking](https://github.com/apache/skywalking){:target="\_blank"}
- [pinpoint](https://github.com/pinpoint-apm/pinpoint){:target="\_blank"}

#### Misc

- [sysstat](https://github.com/sysstat/sysstat){:target="\_blank"} - Performance monitoring tools for Linux
- [Server Status Rust](https://github.com/zdz/ServerStatus-Rust){:target="\_blank"} - Rust 实现的服务器监测
- [uptime kuma](https://github.com/louislam/uptime-kuma){:target="\_blank"} - A fancy self-hosted monitoring tool
- [btop](https://github.com/aristocratos/bpytop){:target="\_blank"} - 改良版本 top
- [netdata](https://github.com/netdata/netdata){:target="\_blank"} - Real-time performance monitoring 是 c / c++ 实现，也支持自己写 Collector 扩展。(比较适合做单机的时时检查用)
- [nmon](https://nmon.sourceforge.net/pmwiki.php) - 用 cli 也支持 csv 导出后的分析。适合单机检查、分析具体问题。

---

### Database

数据库相关知识和工具

#### Key-Value Database

- [Dragon Fly DB](https://dragonflydb.io/){:target="\_blank"} - 类 redis ，看统计比 redis 快，占内存少

#### Time series database

- [GrepTimeDb](https://github.com/GreptimeTeam/greptimedb){:target="\_blank"} - rust 实现的 TS DB

#### [SQLite](https://www.sqlite.org/){:target="\_blank"} 系

- [SQLite Docs](https://www.sqlite.org/docs.html){:target="\_blank"}
- [SQLite Github mirror](https://github.com/sqlite/sqlite){:target="\_blank"}
- [SQLite 源代码解析](https://huili.github.io/sqlite/sqliteintro.html){:target="\_blank"}
- [rqlite](https://github.com/rqlite/rqlite){:target="\_blank"} - Golang 封装 raft + SQLite 实现的分布式数据库


#### [PostgreSQL](https://www.postgresql.org/){:target="\_blank"} 系

- [patroni](https://github.com/zalando/patroni){:target="\_blank"} - python 实现 PG 集群配置工具 (依赖 ETCD )

#### DB tools

- [dbeaver](https://dbeaver.io){:target="\_blank"} - 支持各种数据库的管理工具。基于 Java, JDBC 用 Eclipse 改的界面。社区版本免费。


---

### C/C++

- [abseil](https://abseil.io/){:target="\_blank"} - [abseil-github](https://github.com/abseil/abseil-cpp); [abseil-blog](https://abseil.io/blog/)

---

### Java

- [jodd](https://github.com/oblac/jodd){:target="\_blank"} - 各种工具库的独立实现，不一定最好但都比较小巧。
- [byte-buddy](https://github.com/raphw/byte-buddy){:target="\_blank"} - Runtime code generation

---

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

---

### Github Tools

- [Open Source Software Insight](https://ossinsight.io/){:target="\_blank"} - github 的一些统计
- [giscus](https://giscus.app/){:target="\_blank"} - 基于 github discussions 做的 BLOG 留言系统
- [utteranc](https://utteranc.es/){:target="\_blank"} - 基于 github issue 做的 BLOG 留言系统

---

### OS distribution

- [AlmaLinux](https://almalinux.org/){:target="\_blank"} - CentOS 替代
- [Clear os](https://www.clearos.com/){:target="\_blank"} - 类似 Redhat, CentOS 不过适合 NAS 管理，有一些远程管理工具。
- [scoop](https://scoop.sh/){:target="\_blank"} - Windows package management 

---

### Tutorials

- [CS DIY](https://csdiy.wiki/){:target="\_blank"} - Computer science 自学目录
- [µGo 语言实现(从头开发一个迷你 Go 语言编译器)](https://github.com/wa-lang/ugo-compiler-book){:target="\_blank"} - go 编译器学习
- [Go 语言定制指南](https://github.com/chai2010/go-ast-book){:target="\_blank"} - Go 语法树入门

---

###  Dev-Ops

- [ntfy](https://ntfy.sh/){:target="\_blank"} - 通知系统
- [gotify](https://gotify.net/){:target="\_blank"} - 通知系统
- 分发部署系统: saltstack, ansible, puppet, chef, rudder, fabric, Terraform

---

### Misc

- [ddosify](https://github.com/ddosify/ddosify){:target="\_blank"} - Stress / Loading tests framework
- [xxHash](https://cyan4973.github.io/xxHash/){:target="\_blank"} - 比 MD5 和 SHA1 快出很多的 hash 实现。用于计算内测数据的 hash 比较合适，用来做文件的摘要意义不大，因为瓶颈一般做 disk I/O 上。 [xxHash Github](https://github.com/Cyan4973/xxHash){:target="\_blank"}；[xxHash Golang 实现](https://github.com/cespare/xxhash/){:target="\_blank"}
- [go-guerrilla](https://github.com/flashmob/go-guerrilla){:target="\_blank"} - Mini SMTP server written in golang
- [coreutils rust](https://github.com/uutils/coreutils){:target="\_blank"} - unix core utils 的 rust 实现版本
- [podman](https://podman.io/){:target="\_blank"} - daemonless container engine
- [ttar](https://github.com/ideaship/ttar){:target="\_blank"} - 文本文件打包工具
- [vegeta](https://github.com/tsenart/vegeta){:target="\_blank"} - golang library HTTP API 压测工具
