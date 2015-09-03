---
layout: post
title: "Boost unit test 實踐/練習"
description: ""
category: dev
tags: [dev, Boost, gist, scratch]
---
{% include JB/setup %}

這周上班時被 Azure China 折磨得死去活來。決定業餘時間換換心情，磨練一下自己的基本功。   
作爲一個非計算機專業的人，向來就是個算法 "鶸雞" 來著。
於是乎搞了個基於 Boost unit test 來運行的日常算法測試庫。主要用途:

- 自己日常做題，可以直接記錄在上面。比如: LeetCode 上面刷的題可以慢慢放進去。
- 爲了幫助理解，自己實現(抄)的一些算法，也可以放在裏面。

----

## 基本結構

目前的實現，放在 github 上: [gazlowe](https://github.com/xiongjia/scratch/tree/master/gazlowe){:target="_blank"}

{% highlight bash %}
|~gazlowe/
  |~src/
  | |-g_leetcode.cxx
  | |-g_misc.cxx
  | |-g_misc.hxx
  | |-g_sorting_qsort.cxx
  | `-main.cxx
  |-CMakeLists.txt
  `-README.md
{% endhighlight %}

### Building

用了 CMakeLists.txt 作工程管理。(我在 OS X 和 Windows  上都測試過了)    

*  CMake 的配置中用到了 Boost (最好使用 Boost 1.59+, 因爲 1.59 開始有了
  些 boost/test/data 的東西,雖然目前也沒有去用)
* 我用了 static library 的 Boost 所以 build Boost 時要用 static 並且要
  有 --with-test 來 build Boost unit test。比如:
{% highlight bash %}
b2 link=static runtime-link=static --build-type=complete --with-serialization 
        --with-system --with-thread --with-date_time --with-regex --with-test
        --with-log stage
{% endhighlight %}

### Sources  

Sources 都放在了 `src` folder 中, 基本上一個練習就是一個 unit test case，
一組就是一個 suite (比如: leetcode 算是一個 test suite) 。

- `main.cxx` : 用來放 Boot unit test 的 `main` 函數
- `g_misc.{cxx|hxx}` : 是放一些公用的 data struct 必然 LeetCode 裏很多要用到的 `TreeNode`
- `g_leetcode.cxx` : 準備放 LeetCode 的刷的題 (目前只寫了 3 道簡單的，慢慢來)
- other files: 一些單獨的實現(抄)的算法放在單獨的文件中。目前放了一個 
  `g_sorting_qsort.cxx` 是 Quicksort 的實現。

**注:** 這個結構是暫時的，以後可以會分到一個小 `.cxx` 裏, 比如 `g_leetcode.cxx` 如果過長的話。
具體應該會被 update 在 `README.md` 中。

## 如何使用

Build 之後會得到一個 `gazlowe` ,這個就是 Boost unit test 的入口。
可以用 Test suite 或 具體 Test case 當然也可以執行所有 unit tests。比如:

- 運行所有測試: `gazlowe --log_level=test_suite` 
- 運行 LeetCode Test Suite: `gazlowe --log_level=test_suite --run_test=leetcode`
- 運行 LeetCode 中的 Invert Binary Tree: `gazlowe --log_level=test_suite --run_test=leetcode/invert_btree`

現在内容很少，只是確立個基本結構。以後再慢慢堆。

----

# 最後
個人才智有限至極，唯一能做的就是多花時間練習，積累。
對於一個早已認清自己 "鶸雞" 本質的人來説，現在做事或學習都更偏向于可積累和可操作。


#### 附 Boost unit test C的参考资料

- [Boost 1.59 的 Documentation](http://www.boost.org/doc/libs/1_59_0/libs/test/doc/html/){:target="_blank"}

