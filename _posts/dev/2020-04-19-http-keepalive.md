---
layout: post
title: "How to test HTTP Keep alive is actually working"
description: ""
category: dev
tags: [tips, dev]
---
{% include JB/setup %}

需要需要频繁调用一个第三方的 REST API Server 来获取源数据。因为非常频繁的操作，为了减少开销需要在 Client 端用 HTTP Keep-alive 的方式保持一个长连接。

对应要连接的 HTTP Server 第三方提供，无法保持长连接。为了让对应的第三方 Server 开放者明白用了下面这个方法来测试 HTTP Server 是否提供了 Keep-alive 长连接支持。

---

## 基本原理

使用 curl 来连接 HTTP Server ，并且连续访问同一个 Server 两次以上。通过 curl 的输出 log 来查看有是否只有一个 connection 建立。 curl 命令如下:

```
curl -Iv --keepalive-time 60 http://server-addr:port http://server-addr:port
```

- `-Iv` 用来输出详细 log
- `--keepalive-time` 设置 curl 使用 keepalive 保持 connection 。60 秒超时是默认值。
- `http://server-addr:port http://server-addr:port` 表示连续 2 次访问对应的 server。

### Server 支持 Keep-alive 的输出 log

测试时可以用 Ngnix ，把 `nginx.conf` 中的 `keepalive_timeout` 设置默认是 `75s`。这时 keep alive 在 Server 端保持连接的时间。只要能大于 2 次 连接的间歇时间就可以。（如果设置成 `0` 代表禁用 keep-alive 特性）。   
用 `curl -Iv http://localhost:8200 http://localhost:8200` 。来访问本地的 Nginx。   

在 Log 中会有以下几个要点:    
 - `Re-using existing connection! (#0)` 这句话会在 2 次访问之间出现。表示重用了 connection 。
 - `Connection #0 to host localhost left intact` 在每一次访问后都出现，表示 Connection #0 被保持在了 Connection pool 中。

```
[lexj@home tmp]$ curl -Iv --keepalive-time 60 http://localhost:8200 http://localhost:8200
* About to connect() to localhost port 8200 (#0)
*   Trying ::1...
* Connected to localhost (::1) port 8200 (#0)
> HEAD / HTTP/1.1
> User-Agent: curl/7.29.0
> Host: localhost:8200
> Accept: */*
>
< HTTP/1.1 200 OK
HTTP/1.1 200 OK
< Server: nginx/1.12.2
Server: nginx/1.12.2
< Date: Sun, 19 Apr 2020 03:48:38 GMT
Date: Sun, 19 Apr 2020 03:48:38 GMT
< Content-Type: text/html
Content-Type: text/html
< Content-Length: 1731257
Content-Length: 1731257
< Last-Modified: Sat, 06 Apr 2019 17:04:06 GMT
Last-Modified: Sat, 06 Apr 2019 17:04:06 GMT
< Connection: keep-alive
Connection: keep-alive
< ETag: "5ca8dc06-1a6ab9"
ETag: "5ca8dc06-1a6ab9"
< Accept-Ranges: bytes
Accept-Ranges: bytes

<
* Connection #0 to host localhost left intact
* Found bundle for host localhost: 0x8abf10
* Re-using existing connection! (#0) with host localhost
* Connected to localhost (::1) port 8200 (#0)
> HEAD / HTTP/1.1
> User-Agent: curl/7.29.0
> Host: localhost:8200
> Accept: */*
>
< HTTP/1.1 200 OK
HTTP/1.1 200 OK
< Server: nginx/1.12.2
Server: nginx/1.12.2
< Date: Sun, 19 Apr 2020 03:48:38 GMT
Date: Sun, 19 Apr 2020 03:48:38 GMT
< Content-Type: text/html
Content-Type: text/html
< Content-Length: 1731257
Content-Length: 1731257
< Last-Modified: Sat, 06 Apr 2019 17:04:06 GMT
Last-Modified: Sat, 06 Apr 2019 17:04:06 GMT
< Connection: keep-alive
Connection: keep-alive
< ETag: "5ca8dc06-1a6ab9"
ETag: "5ca8dc06-1a6ab9"
< Accept-Ranges: bytes
Accept-Ranges: bytes

<
* Connection #0 to host localhost left intact
```

### Server 不支持 Keep-alive 的输出 log

测试时可以用 Ngnix ，把 `nginx.conf` 中的 `keepalive_timeout` 设置成 `0` 即可禁用 keep-alive。   
同样用 `curl -Iv --keepalive-time 60 http://localhost:8200 http://localhost:8200` 。来访问本地的 Nginx。   


在 Log 中会有以下几个要点:    
- `Closing connection 0` ; `Closing connection 1` 输出了每一个 Connection 被关闭的 log  ，表示 server 没有 keep-alive 的设置
- 在 log 中会输出 connection 0 和 connection 1 多个连接。

```
[lexj@home tmp]$ curl -Iv --keepalive-time 60 http://localhost:8200 http://localhost:8200
* About to connect() to localhost port 8200 (#0)
*   Trying ::1...
* Connected to localhost (::1) port 8200 (#0)
> HEAD / HTTP/1.1
> User-Agent: curl/7.29.0
> Host: localhost:8200
> Accept: */*
>
< HTTP/1.1 200 OK
HTTP/1.1 200 OK
< Server: nginx/1.12.2
Server: nginx/1.12.2
< Date: Sun, 19 Apr 2020 04:00:15 GMT
Date: Sun, 19 Apr 2020 04:00:15 GMT
< Content-Type: text/html
Content-Type: text/html
< Content-Length: 1731257
Content-Length: 1731257
< Last-Modified: Sat, 06 Apr 2019 17:04:06 GMT
Last-Modified: Sat, 06 Apr 2019 17:04:06 GMT
< Connection: close
Connection: close
< ETag: "5ca8dc06-1a6ab9"
ETag: "5ca8dc06-1a6ab9"
< Accept-Ranges: bytes
Accept-Ranges: bytes

<
* Closing connection 0
* About to connect() to localhost port 8200 (#1)
*   Trying ::1...
* Connected to localhost (::1) port 8200 (#1)
> HEAD / HTTP/1.1
> User-Agent: curl/7.29.0
> Host: localhost:8200
> Accept: */*
>
< HTTP/1.1 200 OK
HTTP/1.1 200 OK
< Server: nginx/1.12.2
Server: nginx/1.12.2
< Date: Sun, 19 Apr 2020 04:00:15 GMT
Date: Sun, 19 Apr 2020 04:00:15 GMT
< Content-Type: text/html
Content-Type: text/html
< Content-Length: 1731257
Content-Length: 1731257
< Last-Modified: Sat, 06 Apr 2019 17:04:06 GMT
Last-Modified: Sat, 06 Apr 2019 17:04:06 GMT
< Connection: close
Connection: close
< ETag: "5ca8dc06-1a6ab9"
ETag: "5ca8dc06-1a6ab9"
< Accept-Ranges: bytes
Accept-Ranges: bytes

<
* Closing connection 1
```

---

## 参考资料

- [How to test HTTP Keep alive is actually working](https://stackoverflow.com/questions/4242145/how-to-test-http-keep-alive-is-actually-working)
- [curl --keepalive-tiem](https://curl.haxx.se/docs/manpage.html#--keepalive-time)
- [Ngnix keepalive_timeout](http://nginx.org/en/docs/http/ngx_http_core_module.html#keepalive_timeout)
