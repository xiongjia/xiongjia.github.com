---
layout: post
title: "JS Promise 的套路"
description: ""
category: dev
tags: [tips, dev, js]
---
{% include JB/setup %}

在 Promise 加入 ES 標準前，俺一直以來處理 async 的方式是使用一些第三方的實現。
比如: 

* [async](https://github.com/caolan/async){:target="_blank"}
* [Promises/A+](https://github.com/then/promise){:target="_blank"}

Promise 加入 ES6 標準后就盡量使用 Promise。 

- 好處:
  * 減少第三方的依賴
  * Promise 的實現相對 async 之類的基於 callback 會有些優勢。   
    比如: 沒有忘記調用 callback 或者 多次 callback 的問題; 
    也可以處理 throw exception 的情況。

- 壞處: 
  * Promise chain 連來來去，如果複雜度高，有時自己會暈。
    有時甚至比 callback hell 更加讓人頭暈。

----

# 套路整理
為了避免日常錯誤,俺把日常會用到的一些套路 ( patterns ) 都演練了一下。
日常用的套路可以分爲: 串行執行 (series); 並行執行 (parallel); 
還有一种複雜一點的 retry 有時會用到。

下面所提到的那些測試的代碼都放在了 Github 上: 

- [js-promise-tests](https://github.com/xiongjia/scratch/tree/master/js-promise-tests){:target="_blank"}

----

## Series: `node test/test_series.js`
* 處理 Task A, B, C。 A, B, C 順序執行, 都結束則執行 Final。   
  {% highlight text %}
  Task A [Pass] -> Task B [Pass] -> Task C [Pass] -> Final
  {% endhighlight %}

* 處理 Task A, B, C。 A, B, C 會順序執行, 如果都結束則執行 Final。
  A, B, C 有失敗則直接執行 Final, 並且報 error。   
  {% highlight text %}
  Task A [Pass] -> Task B [Err] -X-> Task C [Skip]
                      |                           
                      +--> Final [Error]          
  {% endhighlight %}

* 處理 Task A, B, C。 A, B, C 會順序執行, 如果都結束則執行 Final。
  A, B, C 有失敗根據需要可以忽略，只把 Error 記錄。
  依舊繼續往下跑到 Final 。   
  {% highlight text %}
  Task A [Ignore] -> Task B [Ignore] -> Task C [Ignore] -> Final
  {% endhighlight %}

## Parallel: `node test/test_parallel.js`
* 處理 Task A, B, C。 A, B, C 並行執行, 都結束則執行 Final。   
  {% highlight text %}
  Task A [Pass] -+                      
  Task B [Pass] -|-> Final [A,B,C Pass] 
  Task C [Pass] -+                      
  {% endhighlight %}

* 處理 Task A, B, C。 A, B, C 並行執行, 都結束則執行 Final。
  如果有 error 則記錄下來，到最後一起返回給 Final。
  {% highlight text %}
  Task A [Pass] -+                             
  Task B [Pass] -|-> Final [A,B Pass; C Error] 
  Task C [Err ] -+                             
  {% endhighlight %}

## Race - `node test/test_race.js`
Race 和 Parallel 一樣用於處理並行任務。區別在於處理並行任務時, 
Race 只會等到第一個任務成功或失敗，而不等所有的任務結束。
這種套路經常用於 Timeout，比如 Connection 和 Timer 作爲 2 個 Tasks。

* 比如 Task A, B。 A 需要 3 seconds; B 需要 1 second ，
  最後 Final 會等到 B 結束。
  {% highlight text %}
  Task A [Pass (3seconds)] -+
                            |-> Final [B]
  Task B [Pass (1seconds)] -+
  {% endhighlight %}

## Retry `node test/test_retry.js`
固定次數的 Retry 用 Promise 實現比較方便。
* Retry Task A 3 次 后成功:
  {% highlight text %}
  A [Err; 1st] -> A [Err; 2nd] -> A [Pass; 3rd] -> Final
  {% endhighlight %}

* Retry Task A 3 次依舊失敗:
  {% highlight text %}
  A [Err; 1st] -> A [Err; 2nd] -> A [Err; 3rd] -> Final [Err]
  {% endhighlight %}

## Until - `node test/test_until.js`
不固定次數的 retry 用 Promise 實現也不是很方便。
實現了一個在 `test/test_until.js` 裏,也不算很好。

* `exports.untilPassed()` :    
  - 最大 retry 1000 次,每次延遲 10ms
  - 100 次調用后, retryTask 會成功

* `exports.untilErr()` :    
  - 最大 retry 1000 次,每次延遲 10ms
  - 這個 retryTask 永遠不會成功
  - 1000 次后 這個 until 會報錯結束

----

# 最後
一些有關于 JS Promise 或者 Async 的資料:

* [async](https://github.com/caolan/async){:target="_blank"} 
  文檔中的那些 Patterns， 對於 JS Async 有比較好的抽象。

* [You Don't Know JS (book series)](https://github.com/getify/You-Dont-Know-JS){:target="_blank"} 
  中的 "Async & Performance"  和 "ES6 & Beyond"  兩本。

* Mozilla MDN 中對於 Promise 的説明:
  [MDN Promise](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise){:target="_blank"} 

* 中文的 JS Promise 迷你书。有對 Promise 的基礎介紹。
  [JS Promise 迷你书](https://github.com/liubin/promises-book){:target="_blank"} 

