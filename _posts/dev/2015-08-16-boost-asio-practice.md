---
layout: post
title: "Boost ASIO 實踐/練習"
description: ""
category: dev
tags: [dev, Boost, gist, scratch]
---
{% include JB/setup %}

這一段試驗各種 c/c++ 的 I/O Frameworks。
在往前曾經試驗過 [libuv](https://github.com/libuv/libuv){:target="_blank"} 。
當時寫的測試一個 libuv 實現簡單 http server: [roach](https://github.com/xiongjia/scratch/tree/master/roach){:target="_blank"}。

----

這次測試的 Boost ASIO ，爲了方便就只實現了
一個局部功能的 socks5 proxy server (rfc1928)。

目前的實現放在了 github 上: [zeratul](https://github.com/xiongjia/scratch/tree/master/zeratul){:target="_blank"}

- 試驗 Boost ASIO 爲主，所以只簡單實現了 Socks5 , IPv4, No Author 的 Connection command。
- 協議細節可以參看 [rfc1928 - SOCKS Protocol Version 5](https://www.ietf.org/rfc/rfc1928.txt){:target="_blank"}。
- 默認 port 用了 `9090`；目前把 protocol 實現都堆在了 `zeratul.cxx` 裏。
- 可以用 curl 來測試這個 proxy。比如: `curl --socks5 localhost:9090 http://www.boost.org/`
- 對於得 CMakeLists.txt 配置了對於得 Boost ASIO 和 Log，
  並且在 Windows 上用了 boost static library。準備 boost 時可以用如下參數:
{% highlight bash %}
b2 link=static runtime-link=static --build-type=complete 
        --with-serialization --with-system --with-thread --with-date_time 
        --with-regex --with-log stage
{% endhighlight %}

----

# 最後
只是爲了試驗 Boost ASIO 為下一步工作做些準備。
很多 Protocol 的細節都沒有實現出來，有些異常處理也有問題。

