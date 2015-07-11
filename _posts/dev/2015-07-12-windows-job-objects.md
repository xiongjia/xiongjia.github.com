---
layout: post
title: "Windows Job Objects"
description: ""
category: dev
tags: [dev, windows]
---
{% include JB/setup %}

這星期工作中遇到的一個問題，後來是使用 Windows Job Objects 來幫忙解決的。   

工作中的問題是:  

-  一個多 processes 的應用場合。 用一個 Master process 
   管理多個 Worker processes。   
-  由於某些原因 Master processe 可能會意外 crash 或者 termiated。
   在 Master process 終止時，希望所有 Worker processes 同時被釋放。

下面列一下, Job objects  的基本說明和一個 Sample .

----

# 什麼是 Job Objects
在 msdn 上的說明: [A job object allows groups of processes to be managed as a unit.](https://msdn.microsoft.com/en-us/library/windows/desktop/ms684161(v=vs.85).aspx) 可以將一組 processes 關聯道一個 Job object 上進行管理。   

Job Objects 提供了 "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" 設置。可以在 Job Object 關閉時，去殺死關聯的 processes 。


# 基本使用

在 gist 裡寫了一個基本使用的 **Sample**: [gist](https://gist.github.com/xiongjia/a2ba02188674f74c489a)

- 通過 CMake 可以直接編譯這個 Sample
- 一個 process 只能關聯一個 Job。否則會 Windows API 會直接失敗。
- Job object 可以是 unnamed 也可以是 named。Sample 中用的是 unnamed 。
- 用到的 Job Object Options: 
  - "JOB_OBJECT_LIMIT_BREAKAWAY_OK, JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK"
    表示 Worker processes 再開的 process 不會被自動關聯
  - "JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION"
    設置 processes 的 error module 到 SEM_NOGPFAULTERRORBOX。
    防止一些奇怪的對話框。
  - "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE"
    殺死關聯進程，當 Job Object 被關閉
- 用 Sysinternals Suite 的 process explorer 可以觀察對應 process 的
  Job Object.比如下圖中 3 個 notepad.exe 被關聯到了一個 unnamed Job object 上:
![Windows Job Objects]({{ site.url }}/assets/res/img/dev-win-job-obj.png)

