---
layout: post
title: "日常追番中的防卡方法"
description: ""
category: misc
tags: [comic, tips]
---
{% include JB/setup %}

家裏廢棄電視機很多年了。現在日常的學習或娛樂的視頻多出自視頻網站。    
學習向的視頻多出自"油管"。娛樂項的動漫爲主多出自"彈幕"站。

這些資源有時十分卡，嚴重影響我的追番/補番時的心情。
用 mobile/pad 的 client app 是可以下載到本地之後 offline 收看。
不過問題是 mobile/pad 容量有限，有些喜歡的資源經常看好幾遍。
所以我還是希望能夠，在 PC 上 offline 收看這些。
這樣也就不卡，而且不受容量的限制。

# 最終的效果 

- 先看一下學習向的: 從 "油管" 搞得 Modern OpenGL 簡單教程:    

![video-downloader]({{ site.url }}/assets/res/img/tip-video-downloader-01.png)


- 再看一下娛樂向的: bilibili 上搞得 <亚尔斯兰战记> EP16:  

![video-downloader]({{ site.url }}/assets/res/img/tip-video-downloader-02.png)


# 用到的工具

- youtube-dl: [https://github.com/rg3/youtube-dl](https://github.com/rg3/youtube-dl){:target="_blank"}
  - 不要被名字欺騙。這個工具可以下載很多主流網站的視頻，不光是"油管"。   
  它的 docs 裏有列出當前的支持的 sites: [docs/supportedsites.md](https://github.com/rg3/youtube-dl/blob/master/docs/supportedsites.md){:target="_blank"}
  - 這是一個用 python 實現的 tool， 可以用 pip 來安裝。
    (Windows 可以直接在 releases 裏找 .exe; OS X 可以用 Homebrew 安裝)
  - 另外有一個 [you-get](https://github.com/soimort/you-get){:target="_blank"} 是類似實現，
    只是依賴 python 3 ，我切換不便所以目前沒有使用過。不過看 readme 應該也是不錯得。
- ffmpeg: [https://www.ffmpeg.org/](https://www.ffmpeg.org/){:target="_blank"}
  - 主要用來，合併多個 videos 或者是轉換 videos 格式
  - Windows 直接下載 releases 版本，OS X 用 Homebrew。
    Linux 上方法更多就不列舉了，可參考 ffmpeg 網站上的説明
- Biligrab: [https://github.com/cnbeining/Biligrab](https://github.com/cnbeining/Biligrab){:target="_blank"}   
  這是國人做的一個工具，主要有 2 個作用: 
  1. 下載 "彈幕"
  2. 將 "彈幕"  轉化成 .ass 支持位置、色彩的字幕文件
- bypy: [https://github.com/houtianze/bypy](https://github.com/houtianze/bypy){:target="_blank"}   
  Baidu "网盘" 的 client。python 實現可以在 *nix 上用 command line 來操作。

# 基本使用

## "學習向" 視頻
這裡以從 "油管" 下載 Play list 為例:

- 下載 videos 運行: ("接界" 内用戶自己找個外部機器運行吧)    
  `youtube-dl -i --socket-timeout 200 <Play list url>`
- "接界" 内用戶同步到自己這邊用 bypy 同步數據到 Baidu "网盘" 。之後在 "接界" 内下載。
  (這是我目前能想到的較好的過 "接界" 方法)   
  運行下面的命令: (第一次會需要 OAuth 認證,之後就不用了)   
  `bypy upload <files>`
- 注意: 中途可能發生下載失敗，可以看 youtube-dl 的輸出 log。   
  如果是臨時的網絡異常，只要在執行一邊同樣的 `youtube-dl` 命令就可以了。
  它會自己做續傳(從剛才失敗的地方開始再下，不會傻呵呵的從頭在做的。)

## "娛樂向" 視頻
這裏以 youku 和 bilibili 這兩個常用的為例:

### 以 youku 為例: 
- 下載視屏 (注意網路出錯處理等同于上面提到的):     
  `youtube-dl -i --socket-timeout 200 <youku video url>`
- 合併 part files:
  大部分國内 videos 網站都有分片機制，一個視頻可能被分爲了多個幾分鐘的小文件。
  比如下面這個: <彪速宅男> EP 20, 時長 20 多分鐘，被分成了 11 份 ( youku 獨家，其他站應該沒有)

{% highlight bash %}
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part1.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part2.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part3.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part4.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part5.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part6.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part7.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part8.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part9.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part10.flv
|-第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part11.flv
{% endhighlight %}

- 使用下面這個 ffmpeg 方法把這些 part files concat 到一起:    
  `ffmpeg -f concat -i files-list.txt -c copy <output filename>.flv`     
  這裡的 `files-list.txt` 是一個按次序列出 part files 的文本文件，内容如下:
  (我基本使用 `ls` + `vim` 來快速生成這個文件)    

{% highlight bash %}
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part1.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part2.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part3.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part4.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part5.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part6.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part7.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part8.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part9.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part10.flv'
file './第20话 今泉VS御堂筋-XOTAzMDQ1OTA4_part11.flv'
{% endhighlight %}

### 以 bilibili 為例:
- 下載視屏 (注意網路出錯處理等同于上面提到的):     
  `youtube-dl -i --socket-timeout 200 <bilibili video url>`
- 下載 "彈幕"   
  運行: `python biligrablite.py` 之後按照要求輸入 bilibili av 號和第幾 p 的 p 號.
  下載后是一個 .xml 文件，裏面有目前的 "彈幕" 内容，位置，顔色。
- 轉換 "彈幕" .xml 文件到 .ass 字幕   
  運行: `python danmaku2ass2.py -o <output>.ass -s <WidthxHeight> -dm 15 -fs 25 <"彈幕">.xml`
  - `-s <WidthxHeight>` 是指 videos 的 resolution 比如 1920x1080 的視頻就可以用 `-s 1920x1080`
  - `-dm 15` 這裡的 15 是指 "彈幕" 漂過屏幕的速度為 15 秒 (根據需要自行調整)
  - `-fs 25` 指 "彈幕" 字體大小 (根據需要自行調整)

### 轉換 videos 格式 (可選)
國内下到的多數是 `.flv` ，PC 上基本沒有需要去轉換。
VLC; MPlayerX 等都可以支持 .flv + .ass。
如果是想 copy 到 mobile 設備上可能會有需要轉換成 .mp4。   
用下面這個 ffmpeg 命令可以完成這個操作:    
`ffmpeg -i filename.flv -c:v libx264 -crf 19 filename.mp4`

----

# 最後
目前很多操作時手工完成，有待做一個自動化的集成工具。

