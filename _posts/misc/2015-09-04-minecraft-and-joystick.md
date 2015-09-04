---
layout: post
title: "用手柄來玩 Minecraft"
description: ""
category: misc
tags: [tips, game, minecraft]
---
{% include JB/setup %}

某日在玩另一個手柄操作的遊戲時突發奇想如果能用 Joystick 來玩幾個原先的 PC 版遊戲，
(比如: Minecraft 或者 Don't Starve) 應該會比較有意思。類似奔跑、砍樹、挖礦操作感
應該是比較強的。

----

隨後就去找了一下果然是有通用方法。Minecraft PC 版本的操作方式是: Mouse + Keyboard 。    
Minecraft 的 forums 裏的介紹:

- [How to play Minecraft with a controller! PC & Mac](http://www.minecraftforum.net/forums/archive/tutorials/929802-tutorial-how-to-play-minecraft-with-a-controller){:target="_blank"}

介紹了如何 Joystick 操作轉換到 Keyboard 操作。
Windows 上用 [JoyToKey](http://joytokey.net/en/){:target="_blank"}，
在 OS X 上用 ControllerMate 。

----

## Opensource 的實現

后來繼續找了找也有幾個 Open source 的解決方法。
目前我自己用了 [antimicro](https://github.com/Ryochan7/antimicro){:target="_blank"}。

- 有 Windows 和 Linux 的 releases。Windows 上用 portable 的 zip 包，解開后就能用。     
  具體可以參考他的 Release 説明: [antimicro releases](https://github.com/Ryochan7/antimicro/releases){:target="_blank"}。


## 對於 Minecraft 的設置

- 手柄的種類，我自己目前用的是下圖這種常見的 xbox 手柄 。
![xbox-joystick]({{ site.url }}/assets/res/img/tip-mc_js-joystick.png)

- 對於 Minecraft 的設置:
  * 行走方向 ( W, A, S, D / 前，左，后，右) : 轉換到手柄左搖杆
  * 鏡頭方向 (鼠標方向) : 轉換到手柄右遙杆
  * 原先的鼠標左、右鍵: 轉換到手柄 "A" 、"B"
  * 加速跑 ( Left Ctrl ): 轉換到手柄 "RB"
  * 下蹲/潛行 ( Left Shift ): 轉換到手柄 "Y"
  * 跳躍 ( Space ) : 轉換到 "X"
  * 打開儲物箱 ( E ) : 轉換到手柄 "Start" 
  * 切視角 ( F5 ) : 轉換到手柄 "Back"
  * 丟棄物品 ( Q ) : 轉會到手柄 "LB"
  * 切合選中物品 ( 鼠標滾輪 ) : 轉換到手柄 "LT" <-> "RT"

- 下圖是目前的 Minecraft 的設置頁面，打遊戲時保持 antimicro 運行，
  這樣 Joystick 操作就會被轉化為 Mouse & Keyboard 操作

![antimicro]({{ site.url }}/assets/res/img/tip-mc_js-antimicro.png)

----

# 最後

Minecraft 1.8 之後就沒怎麽有空玩了。現在也就偶爾休假時玩玩。

