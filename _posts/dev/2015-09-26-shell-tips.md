---
layout: post
title: "SHELL Tips"
description: ""
category: dev
tags: [tips, dev, shell, bash]
---
{% include JB/setup %}

記錄一些最近折騰厰裏的自動部署腳本，遇到問題和當時的解決方式和具體細節。
主要是從我自己 wiki site 
裏 [shell 的日常備忘](http://xj-labs.net/dev/shell.html){:target="_blank"} 中選出來的一些内容。

----

## 并行执行

Shell Script 的主要工作基本都是去調用各個 commands 去完成的。
所以如果能讓這些 commands 並行執行是會非常有助於提高效率的。

完成这一個工作需要用到 `wait` command。
比如下面這個例子: 用 2 條加了 `&` 的 `sleep` commands 表示 2 個任務。 
`wait` 沒有參數表示等待 2 個 `sleep` 都結束。`sleep` 只是個例子， 
也可以是從網上下載數據或是其他操作。由於並行執行所以應該會快出很多。
{% highlight bash %}
#!/bin/sh
sleep 100 &
sleep 200 &
wait
{% endhighlight %}

也可以讓 `wait` 只等待某一個任務結束。
比如下面這個例子, `$!` 表示第一個 `sleep` 的 process id。
加在 `wait` 的參數裏表示只等待 某個 process。
這 shell script 應該在 100 秒后退出而，第二個 sleep 在 script 退出時還在運行。
{% highlight bash %}
#!/bin/sh
sleep 100 &
first_sleep=$!
sleep 1000 &
wait ${first_sleep}
{% endhighlight %}

舉一個實際工作中的簡單例子。copy 比較大的 files。
如果正常 copy 是串行執行的就是一個完成后再另一個。 
可以多個文件同時 copy 最大程度的發揮出 disk 的 I/O 吞吐量。
比如下面這個例子，從一個列表裏讀出源，執行 `cp`，
最後在用 `wait` 等待所有 copy 任務結束:
{% highlight bash %}
#!/bin/sh
 
dest=/your_dest_folder
 
for file in "bigfile1" "bigfile2" "bigfile3"
do
    cp -v "${file}" "${dest}" &
done
wait
{% endhighlight %}

## debugging methods

實際腳本中，會加一些臨時的調試方法 (比如輸出些只有調試用的 log 或是生成些調試文件）。 
實踐中較好的習慣是保留這些代碼。而不是每次在需要時臨時添加。比如某 test.sh 内容如下:
{% highlight bash %}
#!/bin/bash
function DBG()
{
    [[ "$_DEBUG" == "on" ]] && $@ || :
}
DBG echo "Debug log"
DBG wget -v http://localhost/dbg_file
{% endhighlight %}

* 正常執行 `test.sh`  是會跳過 "DBG" 開頭的語句的
* 需要啓用調試時，只需定義 "_DEBUG" 比如: `_DEBUG=on ./test.sh` 。
  如此便可保留自己的調試代碼，又不干擾生産環境。
* 這裡用到的 `[[ "$_DEBUG" == "on" ]] && $@ || :` 為單行條件語句。
  - "_DEBUG" 為 "on" 時，就執行 `$@` 即 DBG function 的參數。
  - "_DEBUG" 不為 "on" 時，就執行 `:` 。 `:` 在 shell script 是一種空操作，相當於什麽也不做。

## 減少不必要的 Fork

列幾點平時用的到的減少不必要 fork 的方法:

### 減少不必要的 command
盡量挖掘 command 自身的功能，如無必要則不使用多餘的 command。比如:

- `cat <file> | grep <pattern>` - 不好，因爲 `cat` 是多餘的
- `grep <pattern> <file>` - 比之前好，因爲減少了不必要的 `cat` 和用 pipe 傳送數據的開銷。

### 字符串處理

字符串處理時盡量多用 shell 自帶的操作。只是一兩字符串的操作改善不會明顯，
但是如果是在 `while` loop 中的字符串操作，用此法改進就會有較大的意義了。
比如字符串替換: 

- 用了 `tr` 刪除所有數字
{% highlight bash %}
src_str=123abc
echo "${src_str}" |  tr -d   "[:digit:]"
{% endhighlight %}
- 省去 `tr` ，用如下操作可達到同樣效果:
{% highlight bash %}
src_str=123abc
echo "${src_str//[0-9]/}"
{% endhighlight %}
- `sed`, `awk`, `tr` 等都是很強的文本操作，如果不是必須，就不要用。
- strings 操作的例子篇幅很長，就不列在这里了，
  可以參考我的 [shell 的日常備忘](http://xj-labs.net/dev/shell.html){:target="_blank"}  里有一些这方面的例子。

### `[` vs `[[`
`[` 和 `[[` 都可以用作 shell script 的表達式判斷。區別在於:

- `[` 其實是一個 command 會有一次 fork。`[[` 是 shell 内部操作不需要 fork 一個 process。
- `[[` 並不是 posix 標準，默認 shell 應該是不支持的。但目前流行的 bash, zsh 肯定是支持的。
  所以在用 `[[` 時應該把 `.sh` 的第一行 (hashbang) 改爲 `#!/bin/bash`。
- `[[` 支持更多的比較方式，如 RegularExpression & Pattern  matching 只有 `[[` 支持。
  * RegularExpression matching: <br>
    `[[ $name = a* ]] || echo "name does not start with an 'a': $name"`
  * Pattern matching: <br>
    `[[ $name = a* ]] || echo "name does not start with an 'a': $name"`
- 更多 `[` 與 `[[` 的比較參考:  [BashFAQ](http://mywiki.wooledge.org/BashFAQ/031){:target="_blank"} 

## 使用 mirrors 
自動部署的腳本，經常是需要頻繁訪問網絡資源。比如: `apt-get`, `npm` , `gradle` , `maven` 等。
調整到正確的 mirror sites 可以大大加快整個 script 的過程。 
但是一定要用可信任的站點，否則甘願慢一點。比如下面一些用到過的對 China 的 mirrors:

* ubuntu 
  - ubuntu china 的 source : [ubuntu china source](http://wiki.ubuntu.com.cn/%E6%BA%90%E5%88%97%E8%A1%A8){:target="_blank"} 
  - 請一定注意選對自己的 ubuntu 版本
* node
  - npm 目前 taobao 的還算可信: [taobao npm](http://npm.taobao.org/){:target="_blank"} 
  - node-gyp: 如果不做特殊設置 node-gyp 在初次運行時，還是不會去從 mirror site 下載。
    可以用 `node-gyp-install` 來指定下載位置,請參考: [node-gyp-install](https://github.com/mafintosh/node-gyp-install){:target="_blank"} 

## Archiving with tar

`tar` 是常用的打包工具。日常最重要的注意事項是做好 `exclude`。
不需要和不能打包的文件不要打包。常見的問題:  

* 不小心把機器上的 private key 或 password 打包發佈了造成安全隱患。
  有時候這件事的發生是很間接的，難以被察覺。比如: 
  - 把本地 `.git` 目錄打包了，外面目錄裏的證書雖然被排除了可是 git repository 裏有。
  - 打包了 log file, 在 log file 裏有些特殊的 debug logging 把口令留在了那裏。
* 把自己平台特殊的 modules 打包了(比如: node 的 node_modules )，造成其它系統不能正確運行。
* 把 log files 或者臨時數據文件打包了造成，tar 文件的大小增大。

幾种常用的 exclude 的方式: 

* 添加 `--exclude-vcs-ignores` ，這樣 tar 就回去讀 vcs 的 ignores 文件比如: `.gitignore`
* 添加 `--exclude` 參數。比如: 排出 "node_modules" 目錄，
  可以用 `tar czvf <targert>.tgz  <source folder> --exclude node_modules`
* 使用 `--exclude-from` 指定 ignore 配置文件，比如: 
  `tar czvf <targert>.tgz  <source folder> --exclude-from=ignore.txt` 
  這裡 ignore.txt 的内容是一個行文本, `tar` 會讀入這個文本，符合表達式的文件會被直接 exclude 。
  比如下面這個 ignore list 可以排除大部分的通用臨時文件，private key 等: (具體還是要看 project 來作調整)

{% highlight bash %}
.DS_Store
.DS_Store?
.AppleDouble
.LSOverride
Thumbs.db
ehthumbs.db
Desktop.ini
*.swp
*.log
*.pid
*.out
*.tar
*.tgz
*.tar.gz
*.pem
*.srl
*.fp
*.ppk
*.a
*.lib
*.pdb
*.obj
*.tlog
*.exp
{% endhighlight %}

* 更多的 exclude 的方式參考 `tar` 手冊: [gnu tar](http://www.gnu.org/software/tar/manual/html_section/tar_49.html){:target="_blank"} 

----

# 最後

這次給厰裏做的調整時間人力都有限，還有些想要改的都沒時間。比如:

* 原先的代碼結構差，導致代碼多份冗餘。
* 如果改善代碼結構。希望能用一個 unit test framework 
  來做這些 shell script 的單元測試比如: `shunit2`

其他一些 shell 的日常備忘或資源，以後會繼續提交的我的 
[shell 的日常備忘](http://xj-labs.net/dev/shell.html){:target="_blank"}。 

