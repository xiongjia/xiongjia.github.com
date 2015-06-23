---
layout: post
title: "Shell problems"
description: ""
category: dev
tags: [dev, shell, script, leetcode]
---
{% include JB/setup %}

端午小假,閒來無事做了些 [leetcode](https://leetcode.com/) 上 
[shell 分類](https://leetcode.com/problemset/shell/) 得題目。  
這個分類目前總共也就 4 道:   

- [Tenth Line](https://leetcode.com/problems/tenth-line/)
- [Transpose File](https://leetcode.com/problems/transpose-file/)
- [Valid Phone Numbers](https://leetcode.com/problems/valid-phone-numbers/)
- [Word Frequency](https://leetcode.com/problems/word-frequency/)

感覺難度是:如果是筆試一次寫出來，有些還是挺難得。但如果是有機器可以試幾下，
考慮全面一點，Shell 一般也不要求做太大優化得話應該中等難度。
如果不熟 awk 或者不能用 awk 得話感覺
[Transpose File](https://leetcode.com/problems/transpose-file/) 好像有點難，
反正我是用 awk 做地。

--- 

下面列一下，題目和我當時做地。應該不是最優解法,只是解悶。

# [Tenth Line](https://leetcode.com/problems/tenth-line/) 

## 題目
- 要求在 STDOUT 中輸出給定 file 地第 10 行。需要注意地是，
  如果原始文件不到 10 行，應該無 STDOUT 輸出。
- 原文:    
  - How would you print just the 10th line of a file?   
    For example, assume that file.txt has the following content:
{% highlight bash %}
Line 1
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8
Line 9
Line 10
{% endhighlight %}
  - Your script should output the tenth line, which is:
{% highlight bash %}
Line 10
{% endhighlight %}
  - Hint:
    1. If the file contains less than 10 lines, what should you output?
    2. There's at least three different solutions. Try to explore all possibilities.

## 解法
- 我目前的作法，用 "echo" 補 10 個 "\n" 以避免文件不足 10 行。
  用 "head" + "tail" 找到第 10 行。用 Grep 避免空白行的輸出。
{% highlight bash %}
(cat file.txt; for i in {1..10}; do echo -e "\n"; done) | head -n 10 | tail -n 1 | grep . --color=never
{% endhighlight %}
- 用 AWK 也可以比較方便解這個。我比較喜歡寫 Pipe 套 pipe 的，所以沒有用 AWK。
  基本思路應該是: AWK Action section 查看 NR 為 10 的 Save 在某個 var 裡。
  在 END Action 中 print 出來。

# [Transpose File](https://leetcode.com/problems/transpose-file/)
## 題目
TODO

# [Valid Phone Numbers](https://leetcode.com/problems/valid-phone-numbers/)
## 題目
TODO

# [Word Frequency](https://leetcode.com/problems/word-frequency/)
## 題目
TODO

