---
layout: post
title: "VIM Encryption"
description: ""
category: dev
tags: [dev, vim, encryption]
---
{% include JB/setup %}

個人是一個 VIM 用戶，很多東西都用 Vimwiki 來記錄。   
(比如: 我自己的 VIM Wiki [web site](http://xj-labs.net/){:target="_blank"} [source code](https://github.com/xiongjia/recycle.bin){:target="_blank"} ) 

我有一部分私人事務的 wiki 是存放在 Dropbox 上的。
爲了防止監控我希望 VIM 可以加密這些存儲文件。
VIM 作爲最強的編輯器之一，當然可以做這些的。

主要可以參考下面這篇 VIM Online wiki 上的手冊:

- [Encryption](http://vim.wikia.com/wiki/Encryption){:target="_blank"}

----

## 基本使用
主要通過修改 `cryptmethod`/`cm`, `key` 這 2 個 vim options 來操作。
可用 Vim help `:help cryptmethod` 和 `:help key` 來找到手冊。
(如果不熟 Vim 的基本 options 操作可以參考 Vim 手冊 `:help options` )

- 設置加密算法 - `:set cm=blowfish2` 。    
  Vim (7.4.399+) 自帶有 3 种加密算法: zip; blowfish; blowfish2。
  blowfish2 是目前推薦用的加密算法, 其他 2 個 (zip; blowfish) 
  如果不是因爲要兼容老版本 Vim 就不要去用了。   
  查看當前加密算法用 `:set cm?`。 
- 加密一個文件，可以用 2 种方法
  - `:X` 大寫的 'X' 命令，Vim 會提示用戶輸入 `key` 即口令
  - `:setlocal key=<your password>`, Vim Save file 時會檢查 `key` option 如果存在,
    則用該 `key` 為口令加密。
- 打開一個加密文件，打開加密文件時會讓你輸入 `key`，
  也可以用 `setlocal key=<your password>` ，隨後用 `:e` reload 一下。
- 清空口令 - `:setlocal key=` ，清空口令后再次 save 的文件是明文。


## 注意事項

- [blowfish](https://en.wikipedia.org/wiki/Blowfish_%28cipher%29){:target="_blank"} 
  - 這是一個位操作爲主的算法, 對於純文本應該是 高效的。
  - 會有隨機種子。同樣的 file content 加密 2 次，應該不會產生同樣的結果。   
    (這可以 保證，別人不能通過比較加密結果猜測内容)
- 用 `:setlocal key=<your password>` 設置 password 時，
  Vim 可以保證 password 不出現在 command history 裏。 
  用 `:setlocal key?` 查看當前 password 也是不能看到你的口令的。
- 千萬不要把你的 `:setlocal key=<your password>` 放在 .vimrc 裏。
  用 shell 啓動時，如果用了 `:setlocal key=<your password>` 的話，
  也千萬記住，這個 password 可能會被 bash/zsh 之類的 history file 記錄。

## 第三方加密工具/算法

- 可以參考 Vim Online Wiki 中這部分的介紹: [Encryption](http://vim.wikia.com/wiki/Encryption){:target="_blank"} gpg 部分的介紹。
- 如果用了 gpg 的話，swap file; undo file 之類需要自己處理一下。

----

# 最後

自己也是在一直學習 VIM 的:

- 一些自己日常的備忘，在我的 Vimwiki 中 (大多數手冊裏抄的): 
  [My Vimwiki](http://xj-labs.net/dev/edit.html){:target="_blank"}
- 也寫過一個 Vim Plugin，用來刷 Fanfou 的:
  - 代碼: [vim-fanfou](https://github.com/xiongjia/vim-fanfou){:target="_blank"}
  - 説明文檔: [vim-fanfou](http://xj-labs.net/dev/vim-fanfou.html){:target="_blank"}

