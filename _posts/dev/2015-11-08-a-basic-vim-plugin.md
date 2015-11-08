---
layout: post
title: "一個基本的 VIM Plugin"
description: ""
category: dev
tags: [tips, dev, vim]
---
{% include JB/setup %}

這是俺在創建 [vim-fanfou](http://www.vim.org/scripts/script.php?script_id=4972){:target="_blank"} 這個 VIM Plugin 時對 VIM Plugin 做的一些實踐。

VIM 自帶的 Script 有很強的文本處理能力，也可以方便的和 VIM Buffer 交互。
但是缺點是 VIM Script 其他功能不是很強，比如：不能方便的作 Network I/O 等。
解決這個問題經常用的方法至少有兩個:

1. 利用外部另一個 process (如 curl, wget) 去作這些操作。缺點是:
   * 需要用戶配置好這些。比如在 Windows 上可能需要額外安裝 curl, wget 
     到 %PATH% 中能找到的目錄。
   * 出錯處理困難，比如 curl/wget 突然 crash 了，或者 I/O Timeout 了不好處理。
2. 另一種方式是用 VIM 與其它 scripts (比如: Python, Ruby, Lua) 交互。
   用 VIM Script 實現接口，用 Python/Ruby 等去實現功能。這個方法也有缺點:
   * VIM 編譯時需要啓用 Python 2/3 接口。

自己主要用的都是第二种方式。用 Python 來寫具體的實現，做 Unit tests。
用很少的 VIM Script 來做接口處理。


----

下面列一些當時的實踐和資料。

## 一個簡化了的 Sample
在俺的 gist 中,寫了個簡化了的 Sample 來説明 VIM Script 和 Python 是怎麽交互的。   
參考: [vim-python-script](https://gist.github.com/xiongjia/64e1353afb9415e85479){:target="_blank"}

説明事項 (在代碼註釋裏也有説明):

- 如何加載這個 Sample
  1. 把 Sample 中的 my-vim-plugin.py & my-vim-plugin.vim 放在一個目錄裏。
  2. 用 VIM 打開 my-vim-plugin.vim 
  3. 運行 "so %" 
- 加載這個 plugin 后調用 "MyTestFunc()" 這個 Plugin 
  就會調用 my-vim-plugin.py 裏的 script 把 VIM & python 的版本，
  process id 輸出到當前 buffer 中。

有幾個重要的地方:

- my_vim_plugin.vim 中有 `python ...` 或者 `python << endOfPython ...  endOfPython`
  這樣的代碼段。這兩個方式都是 VIM Script 中調用 Python Script。
  前者表示執行一行，後者表示執行一段。
- my_vim_plugin.vim 中有 `python sys.path.append(vim.eval('expand("<sfile>:h")'))`:   
  這裡是爲了把 my_vim_plugin.vim 所在的目錄添加到 VIM import 的路徑裏。這樣
  之後執行 `import my_vim_plugin as myVimPlugin` 就會正確加載 my_vim_plugin.py。
- my_vim_plugin.vim 中有 `import vim` 。 `vim` 是 VIM 輸出給 Python 的一個 module。
  Python 可以通過它來對 VIM 作操作，比如往 VIM Buffer 中做輸出。
  具體可以參考 VIM 文檔: `:help if_pyth.txt`

## 一些資料
- 一個 "油管" 上的教學 video。這是個很好的視頻，演示了如何用 Python 寫一個 VIM plugin:
  * 視頻地址: [Writing Vim plugins with Python](https://www.youtube.com/watch?v=vMAeYp8mX_M){:target="_blank"}
  * 其用到的 Sample 的 github 地址: [vim-plugin-starter-kit](https://github.com/JarrodCTaylor/vim-plugin-starter-kit){:target="_blank"}

- 俺之前寫 [vim-fanfou](http://www.vim.org/scripts/script.php?script_id=4972){:target="_blank"} 時的代碼和筆記:
  - [vim-fanfou srource code](https://github.com/xiongjia/vim-fanfou){:target="_blank"} 
  - [vim-fanfou 筆記備忘](http://xj-labs.net/dev/vim-fanfou.html){:target="_blank"} 

----

# 最後

- VIM 現在已經是俺日常工作/生活的重要部分了。
  俺自己的 [wiki site](http://xj-labs.net/){:target="_blank"} 也是拿 Vim Wiki 改的。   
  ( 關於 VIM 的一些日常總結，俺一般寫在這裡裏: [Wiki For Edit](http://xj-labs.net/dev/edit.html){:target="_blank"} )
- VIM 本身也是個在不斷的進化的工具，觀察 VIM 在 github 上的倉庫 [vim](https://github.com/vim/vim){:target="_blank"} 。每天都會用很多 pull requests。
- 也希望有更多的人能寫出好玩的 VIM Plugin。無論是用 Python 寫還是直接用 VIM script 寫。

