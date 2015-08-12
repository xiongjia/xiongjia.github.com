---
layout: post
title: "Shell problems"
description: ""
category: dev
tags: [dev, shell, script, leetcode, scratch]
---
{% include JB/setup %}

端午小假,閒來無事做了些 [leetcode](https://leetcode.com/) 上 
[shell 分類](https://leetcode.com/problemset/shell/) 得題目。  
這個分類目前總共也就 4 道:   

- [Tenth Line](https://leetcode.com/problems/tenth-line/){:target="_blank"}
- [Transpose File](https://leetcode.com/problems/transpose-file/){:target="_blank"}
- [Valid Phone Numbers](https://leetcode.com/problems/valid-phone-numbers/){:target="_blank"}
- [Word Frequency](https://leetcode.com/problems/word-frequency/){:target="_blank"}

感覺難度是:如果是筆試一次寫出來，有些還是挺難得。但如果是有機器可以試幾下，
考慮全面一點，Shell 一般也不要求做太大優化得話應該中等難度。
如果不熟 awk 或者不能用 awk 得話感覺
[Transpose File](https://leetcode.com/problems/transpose-file/){:target="_blank"} 好像有點難，
反正我是用 awk 做地。

下面列一下，題目和我當時做地。應該不是最優解法,只是解悶。

--- 

## Tenth Line

### 題目   
   [Tenth Line](https://leetcode.com/problems/tenth-line/){:target="_blank"}
   ( https://leetcode.com/problems/tenth-line/ )

- 要求在 STDOUT 中輸出給定 file 地第 10 行。
- 需要注意地是，如果原始文件不到 10 行，應該無任何 STDOUT 輸出。

### 解法
- 我目前的作法:
  1. 用 "echo" 補 10 個 "\n" 以避免文件不足 10 行。
  2. 用 "head" + "tail" 找到第 10 行。
  3. 用 Grep 避免空白行的輸出。

  具體如下:
{% highlight bash %}
(cat file.txt; for i in {1..10}; do echo -e "\n"; done) | head -n 10 | tail -n 1 | grep . --color=never
{% endhighlight %}

### 其它
- 用 AWK 也可以比較方便解這個。我比較喜歡寫 pipe 套 pipe 的，所以沒有用 AWK。
  基本思路應該是: AWK Action section 查看 NR 為 10 的 Save 在某個 var 裡。
  在 END Action 中 print 出來。

## Transpose File

### 題目  
   [Transpose File](https://leetcode.com/problems/transpose-file/){:target="_blank"}
   ( https://leetcode.com/problems/transpose-file/ )

- 要求 text file 的行列互換

### 解法
- 我目前的作法是用 awk。 
  1. 在 action section 中，把 text 的 fields 放到一個 2 維數組中。
  2. 在 end section 中，按要求把它做輸出。

  具體如下:
{% highlight bash %}
awk '{ if (max_nf < NF) max_nf = NF; max_nr = NR; for (x = 1; x <= NF; x++) vec[x, NR] = $x; } END { for (x = 1; x <= max_nf; x++) { for (y = 1; y <= max_nr; y++) { if (x > 1 && y == 1) { printf("\n"); } if (y == 1) { printf("%s", vec[x, y]); } else { printf(" %s", vec[x, y]); } } } }'  file.txt
{% endhighlight %}

## Valid Phone Numbers

### 題目
   [Valid Phone Numbers](https://leetcode.com/problems/valid-phone-numbers/){:target="_blank"}
   ( https://leetcode.com/problems/valid-phone-numbers/ ) 

- 按要求過濾符合條件的 Phone numbers

### 解法
- 這題相對簡單，用 Grep 的 Regular express 寫一個符合條件的表達式就可以。  
  具體如下:
{% highlight bash %}
cat file.txt | grep -E "(^[0-9]{3}-[0-9]{3}-[0-9]{4}$|^\([0-9]{3}\) [0-9]{3}-[0-9]{4}$)" --color=never
{% endhighlight %}


## Word Frequency

### 題目  
   [Word Frequency](https://leetcode.com/problems/word-frequency/){:target="_blank"}
   ( https://leetcode.com/problems/word-frequency/ ) 

- 統計 text 文件中，單詞出現的次數

### 解法
- 這題目用 awk 應該也可以方便的做出來。目前還是喜歡用 pipe 套 pipe 的寫法。
  1. 用 tr 把單詞分行。
  2. 用 grep 排除空白。
  3. 用 sort + uniq 排序。
  4. 用 awk 調整 uniq 的輸出
{% highlight bash %}
echo -e `cat words.txt` | tr " " "\n" | grep . --color=never | sort -n | uniq -c | sort -nr | awk '{printf("%s %s\n",$2,$1)}'
{% endhighlight %}

---

# 最后
Leetcode 非常好玩， [shell 分類](https://leetcode.com/problemset/shell/){:target="_blank"} 只有這 4 道。
Database 分類，也挺好的。等多刷幾題後再總結一下。

