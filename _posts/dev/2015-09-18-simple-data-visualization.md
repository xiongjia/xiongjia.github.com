---
layout: post
title: "初級 Data Visualization"
description: ""
category: dev
tags: [tips, visualization, gnuplot]
---
{% include JB/setup %}

記錄一下以前數據可視化工具的初級使用方式。    
主要是用 [gnuplot](http://gnuplot.info/){:target="_blank"} 將 .csv 中的數據，整合成圖形輸出。 
( 安裝直接參考: [gnuplot](http://gnuplot.info/){:target="_blank"} 上的説明。）

----

擧個實際的例子來看這個問題。用中國主要城市的空氣污染指數 (AQI) 來做數據。
比較幾個典型城市的 AQI。

## 數據來源
從 github 倉庫 [AQI](https://github.com/feelinglucky/AQI){:target="_blank"} 
下到的 .csv 。大致格式如下:
{% highlight bash %}
13,650100,乌鲁木齐,75,1,2000-06-05
15,110000,北京,116,1,2000-06-05
16,120000,天津,81,1,2000-06-05
18,140100,太原,155,1,2000-06-05
20,210100,沈阳,93,1,2000-06-05
24,310000,上海,63,1,2000-06-05
25,320100,南京,73,1,2000-06-05
37,410100,郑州,98,1,2000-06-05
40,440100,广州,70,1,2000-06-05
38,420100,武汉,69,1,2000-06-05
{% endhighlight %}

- 這個 csv 的列是: 行號,城市代號,城市名,污染指數,污染類型,時間
- 挑選 北、南、中三個城市: 上海 (310000); 北京 (110000); 广州(440100)。

## 生成各個城市的數據

簡單的用 `grep` 來生成 3 個，城市的 .csv ,比如: (aqi.csv 就是之前下載到的 AQI 數據)
{% highlight bash %}
grep "^[0-9]*,110000,*" aqi.csv  > bj.csv
grep "^[0-9]*,310000,*" aqi.csv  > sh.csv
grep "^[0-9]*,440100,*" aqi.csv > guangzhou.csv
{% endhighlight %}

## 用 gnuplot 生成對比

- X 軸為日期,格式 '%Y-%m-%d'。日期範圍為 2010-02-01 至 2015-02-01。
- Y 軸為污染指數。
- plot command 用 csv 的第 6 列和第 4 列，做 3 個城市的 .csv 數據輸出。

{% highlight bash %}
# set graph format
set title "AQI"
set grid y
set xlabel "日期"
set ylabel "污染"

# set csv data
set datafile separator ","
set timefmt '%Y-%m-%d'
set xdata time
set format x "%Y-%m-%d"
set xrange["2010-02-01":"2015-02-01"] 

# creating the result
plot "sh.csv" using 6:4 smooth sbezier \
        with lines title "Shanghai" linecolor rgb "blue", \
     "bj.csv" using 6:4 smooth sbezier \
        with lines title "Beijing" linecolor rgb "red", \
     "guangzhou.csv" using 6:4 smooth sbezier \
        with lines title "Guangzhou" linecolor rgb "green"
{% endhighlight %}


## 輸出結果

大概輸出結果如下:

紅線是北京，綠綫是廣州，藍綫是上海。看來是越南方空氣越好些。

![gnuplot]({{ site.url }}/assets/res/img/dev-dvisu-gnuplot.png)

----

## 最後
初級入門用法，還有不同的作圖命令，可以參考 gnuplot 的手冊和自帶的 samples 
(安裝目錄 `gnuplot/demo` 下)

