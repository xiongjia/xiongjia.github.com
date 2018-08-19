---
layout: post
title: "Build Vim on Windows"
description: ""
category: dev
tags: [tips, dev, vim]
---
{% include JB/setup %}

最近升级系统，顺便重新部署了 Windows 开发环境。
顺便把 VIM 在 Windows 上编译的过程记录一下。

---

目的是把 vim version 8 的 Windows 64 版本编译出来。

## Dependencies
- Microsoft Visual Studio ( e.g. VS 2017 Community )
- Python v2.7
- Windows SDK v7.1

MS VS 应该是可以用任何版本的。 Python 只能用 2.7 ，Python 3 会有编译错误。
Windows SDK 一定要 v7.1 ，因为 VIM Windows 编译是用 `namke` 的。而 v7.1 包
含有 VIM nmake 的 template。

## Build scripts
目前把 Build scripts 提交在了这里: 
[Build Vim in Windows](https://github.com/xiongjia/scratch/tree/master/vim-win-building)

```
~ vim-win-building/
  + build/
  + dest/
  + vim-src/
```
- `build` - 编译脚本
- `vim-src` - vim source [https://github.com/vim/vim](https://github.com/vim/vim)
- `dest` -  输出目录


### Build Settings
所有设置都写在 `configure.cmd` 中。
```
set WIN_SDK=D:\app\Microsoft SDKs\Windows\v7.1\Include
set VS_2017="C:\Program Files (x86)\Microsoft Visual Studio\2017"
set VS_VARS=%VS_2017%\Community\VC\Auxiliary\Build\vcvarsall.bat
set NMAKE=%VS_2017%\Community\VC\Tools\MSVC\14.14.26428\bin\Hostx64\x64\nmake
set PY2_HOME=D:\app\py\python27
set VIM_DEST=.\dest

set FEATURES=BIG
```

## Usage:
- Enable building settings: `.\build\configure.cmd`
- Building vim via MS nmake: `.\build\build.cmd`
- Clean building files: `.\build\build.cmd clean`
- Copy Vim files to dest folder: `.\build\copy-vim.cmd`

## 参考资料
- [Building vim on windows](http://blog.mgiuffrida.com/2015/06/27/building-vim-on-windows.html)

