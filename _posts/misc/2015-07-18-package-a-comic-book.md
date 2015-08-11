---
layout: post
title: "如何打包本子"
description: ""
category: misc
tags: [comic, tips]
---
{% include JB/setup %}

這裡主要記錄一下，我日常是怎麽把下載下來的漫畫打包到 pdf 。   
隨後在上、下班路上或者其它閒暇時間就可以 iPad or Kindle 上看了。

----

# 成品

自己打包不受限制，比一些動漫下載 app 要自由得多。

- 在 PC 上的效果:    
![comic-pdf]({{ site.url }}/assets/res/img/tip-comic-pdf-pc.png)

- 在 iPad (左) 和 Kindle (右) 上的效果:   
![comic-pdf]({{ site.url }}/assets/res/img/tip-comic-pdf-ipad.png)
![comic-pdf]({{ site.url }}/assets/res/img/tip-comic-pdf-kindle.png)

# 工具 
用到的工具主要有:

- [ChainLP](http://no722.cocolog-nifty.com/blog/chainlp/){:target="_blank"} - 最主要的工具。將一組圖片生成 PDF 格式 。
- [briss](http://sourceforge.net/projects/briss/){:target="_blank"} - PDF 裁減 (cropping) 工具。
- Multiple Files Renamer - 
  Windows 上基本使用 PowerShell 就大概夠了。*nix 可以用 shell 裏的一些工具。

## ChainLP
- 下載 [http://no722.cocolog-nifty.com/blog/chainlp/](http://no722.cocolog-nifty.com/blog/chainlp/){:target="_blank"}
- 使用方式如下圖: (其核心是 2 點輸入和輸出)
  1. 決定輸入的圖片組:    
     按右側紅框標出的 **Input** 按鈕。選擇漫畫圖片所在的目錄。
     操作完畢后，左側文件框會列出這些，一般是按照 file name 排序。
     彩色圖片的 Fig 會被自動選中, 一般不需要手工操作。
  2. 決定輸出:
     中間紅線表示輸出位置 ( Fixed output folder )，選擇想要的目錄。
     右側的紅框標記的 *output* 一組選項是用來決定輸出的格式的。我這裏選擇的是 pdf。
     設置完畢后按右側標記出的 *Output* 按鈕。就會生成出對應的 pdf。
  3. 其它參數可以在右側中下方找到。比如 Size, Title 等。一般用默然的也可以。 
![comic-pdf]({{ site.url }}/assets/res/img/tip-comic-pdf-clp.png)

## briss
用 ChainLP 生成的 PDF 在周圍可能會有一圈留白，用 briss 可以裁減掉這些留白。

这步操作不是必須的，但是它可以使得圖片佔屏幕更大比例。
對於 Kindle 閲讀有比較大的幫助。

- 下載 briss : [http://sourceforge.net/projects/briss/](http://sourceforge.net/projects/briss/){:target="_blank"} 
  (注: briss 本身是 Java 實現，所以運行環境必須有 Java runtime。)
- 使用: 
  1. 運行 briss-0.9.exe (這裏用的是 version 0.9)  
  2. 打開 ChainLP 生成的 PDF。
     過程中會彈出一個輸入框，讓你選擇不需要 cropping 的頁號。
     (比如漫畫中有些彩頁不想被 cropping )
  3. 打開后 briss 會自動分析對應的 pdf,並顯示一個 cropping 前後的大小比較。
  4. 要生成 cropping pdf 就是選擇 Menu 中的 Action -> Crop 
     就會生成一份對應的 cropping pdf。

## Multiple Files Renamer
下載或抓取下來的漫畫，一章大概有十或幾十頁不等。為每一個章節作一個 pdf 實在是不上算。
所以往往把多個章節打包成一個 pdf。這樣才耐看。

這時會遇到一個問題下載下來的漫畫往往是下面這種結構的:
{% highlight bash %}
|~001话/
| |-001.jpg
| |-002.jpg
| |-003.jpg
| `-... (other files)
|~002话/
| |-001.jpg
| |-002.jpg
| |-003.jpg
| `-... (other files)
|~003话/
| |-001.png
| |-002.png
| |-003.png
| `-... (other files)
|~... (Other folders)
{% endhighlight %}

上面這種結構，ChainLP 逐一打開，操作不便。
所以目標是先將這些圖片整合成如下這種**平坦有序**的結構:
{% highlight bash %}
|~Root
| |-001话_001.jpg
| |-001话_002.jpg
| |-001话_003.jpg
| |-... (other files 001话)
| |-002话_001.jpg
| |-002话_002.jpg
| |-002话_003.jpg
| |-... (other files 002话)
| |-003话_001.jpg
| |-003话_002.jpg
| |-003话_003.jpg
| |-... (other files 003话)
| |-...
{% endhighlight %}

基本常用下面的方式來做這樣的批量 renaming files。

- 在 Windows PowerShell 中:
  1. 先把 .jpg/.png files 改名。新的 file name 等於 "所在目錄名" + "-" + "原始文件名"。   
     比如: "001话/001.jpg"  ==> "001话/001话-001.jpg"
  2. 把所有 .jpg/.png files 移動到輸出目錄 (這裏是 "E:/data/root/"):
{% highlight bash %}
Get-ChildItem -Recurse | Where { $_.Extension -eq ".jpg" -Or $_.Extension -eq ".png"  } | Rename-Item -Path { $_.FullName } -NewName { $_.Directory.Name + "-" + $_.Name }

Get-ChildItem -Recurse | Where { $_.Extension -eq ".jpg" -Or $_.Extension -eq ".png"  } | Move-Item -Path { $_.FullName } -Destination { "E:/data/root/" + $_.Name }
{% endhighlight %}

- 在 *nix:
  把 find 找到的所有 .png/.jpg 用 mv 移送到輸出 folder 中(這裏是 `./out` folder)。
  新的文件名和 PowerShell 時一樣: "parent dirname" + "-" + "original file name"。
{% highlight bash %}
find . -type f -name '*.jpg' -o -name '*.png' | while read -r file; do mv -v $file ./out/$(dirname -- "$file")-$(basename -- "$file"); done;
{% endhighlight %}

有些時候可能有些下到的包，命名就是混亂的。比如:
{% highlight bash %}
|~001话/
| |-1.jpg
| |-10.jpg
| |-11.jpg
| |-... (other files)
| |-2.jpg
| |-20.jpg
| |-... (other files)
{% endhighlight %}

這樣按 File name 不能正確排列，會導致 pdf page 錯亂。
必須增加 "0" 使得所有數字位數相同 。
可以用下面的方法。

- 在 Windows PowerShell 中，用 regular express 來批量補 "0"
{% highlight bash %}
Get-ChildItem -Recurse | Where { $_.Extension -eq ".jpg" -Or $_.Extension -eq ".png" } | Rename-Item -Path { $_.FullName } -NewName { [regex]::match($_.Name, '(\d+)').Groups[1].Value.PadLeft(5, "0") + $_.Extension }
{% endhighlight %}

- 在 *nix 中, 用 rename 來批量補 "0":
{% highlight bash %}
rename  's/(\d+)\.(png|jpg)$/sprintf("%05d.%s", $1, $2)/e' *.{png,jpg} 
{% endhighlight %}

----

# 結束
以上大概是我目前在 "本子" 打包過程中的一些方式。
最終目標是一個命令全自動化。現在還是有少數步驟需要手工操作,有待優化。

