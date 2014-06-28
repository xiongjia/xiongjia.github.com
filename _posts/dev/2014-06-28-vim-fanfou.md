---
layout: post
title: "Vim Fanfou"
description: ""
category: dev
tags: [dev, vim, python]
---
{% include JB/setup %}

如同 Fanfoun 是 Twitter 的山寨， [vim-fanfou](https://github.com/xiongjia/vim-fanfou) 也只是我對 [TwitVim](https://github.com/vim-scripts/TwitVim) 一次初級山寨。 

下午标记了第一个 Release 的 Tag ：

- 在 Github 上: [vim-fanfou](https://github.com/xiongjia/vim-fanfou/)
- 在 Vim.org 上: [vim-fanfou](http://www.vim.org/scripts/script.php?script_id=4972)

### 原型
这个 Plugin 使用方式基本是参考 [TwitVim](https://github.com/vim-scripts/TwitVim) 的。    
实现的原型则是我早先 Gist 上的 2 个 Tests 的改进、修正和整合:

- Vim Script 中使用 Python: [gist](https://gist.github.com/xiongjia/64e1353afb9415e85479)
- Python Fanfou API Tests: [gist](https://gist.github.com/xiongjia/b8893dc5eb5bbb04cfbc)

### 代码和文档
- 代码目前都在 github 上: [vim-fanfou](https://github.com/xiongjia/vim-fanfou/)
- 开发总结的 Wiki: [Vim-Fanfou Wiki](http://xj-labs.net/dev/vim-fanfou.html)

### 目前的版本

- 下面这 2 个 vim buffer 中，上方那个就是 Vim Fanfou 的 Timeline buffer。而下方是 TwitVim 的 buffer。    
![VimFanfouBuf]({{ site.url }}/assets/res/img/dev-vim-fanfou-buf.png)

- 总体可以让我一边写代码一边看 timeline 。  
![VimFanfouWin]({{ site.url }}/assets/res/img/dev-vim-fanfou-win.png)


### 目前的版本沒能支持的:
 * Syntax:
   - "@username" 沒有做 match
   - "#topic#" 沒有做 match 
 * Network:
   - HTTP Proxy authorization 沒有支持 ( 目前可以用沒有 authorization 的 http proxy ) 
 * 使用方面:
   - 支持更多 Fanfou API 的操作. ( 目前只有 View HOME Timeline 和 Post status ）
   - 支持大於 60 條的 home timeline
   - 支持 Web browser 種類設定 ( 目前只能是當前 OS default browser )
   - 支持直接從 VIM buffer 打開一個 url 
 * 開發流程上:
   - 需要增加 Python unit tests 

