---
tags: [tech,oss,vnstat]
---

# 摘要

vnStat 用于统计机器上的网络流量。支持 Linux 和 BSD 系统。

## 资源

- [Docs](https://humdi.net/vnstat/){:target="_blank"}
- [Source code on github](https://github.com/vergoh/vnstat){:target="_blank"}

## 组成和基本原理

vnStat 基本由 3 部分组成:  *vnStatd*, *vnStat*, *vnStati*。

- vnstatd: 是一个 Daemon 后台进程，启动后会定期收集网络数据，并把历史数据写入一个 SQLite Database File 中。
- vnstat: 是一个命令行工具，从 vnStatd 生成的 SQLite Database 中把网络流量的统计信息得出。
- vnstati: 基于 GD Library 用于生产统计信息的图表输出。

### Linux 上的流量统计

Linux 系统的统计信息主要是通过读取 sysfs 和 procfs 中的信息得到的。具体需要参考下面这篇 Linux Kernel doc:

- [Interface statistics](https://www.kernel.org/doc/html/latest/networking/statistics.html){:target="_blank"}

### BSD 上的流量统计

目前版本的 MacOS 也可以使用。主要用 `getifaddrs` 的系统调用。参考下面这篇 OpenBSD 的文档:

- [getifaddrs](https://man.openbsd.org/getifaddrs){:target="_blank"}

### DB Scheams

主要的实现中 `dbsql.c` 中的 `db_create()` 方法中。

```SQL
# 用来存放网卡设备相关的信息
CREATE TABLE info(
    id INTEGER PRIMARY KEY, 
    name TEXT UNIQUE NOT NULL, 
    value text not null);

# 网卡和对应  rx, tx 统计
create table interface (
	id int, name text unique, 
    alias text, 
    active int, 
	created datetime, updated datetime, 
    rxcounter int, txcounter int, 
	rxtotal int, txtotal int);

#  %s 为 6 个一样的 tables {"fiveminute", "hour", "day", "month", "year", "top"}
# 用来做统计
create table %s (
    id int, interface int, 
    date datetime, 
    rx int, tx int);
```

## Misc

- [libgd](https://libgd.github.io/){:target="_blank"} - 用于生成统计信息的图表

## 同类

- [ntop](https://www.ntop.org/){:target="_blank"}
- [darkstat](https://unix4lyfe.org/darkstat/){:target="_blank"} -  基于 tcpdump
- [mrtg](https://oss.oetiker.ch/mrtg/){:target="_blank"} - 基于 SNMP 协议获取。所以正确配置可以支持 Windows OS。
- [bwm-ng](https://github.com/vgropp/bwm-ng){:target="_blank"} - (disk io & network monitory)
- [iftop](https://www.ex-parrot.com/pdw/iftop/){:target="_blank"} - 基于 tcpdump
- [iptraf-ng](https://github.com/iptraf-ng/iptraf-ng){:target="_blank"}
