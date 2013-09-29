---
layout: post
title: "MS UIAutomation in PowerShell"
description: ""
category: dev
tags: [dev, MS, UIA, UIAutomation, PowerShell, .Net]
---
{% include JB/setup %}

并没有什么特别之处，只是记录一下在 PowerShell 中使用 MS UIAutomation 的基本方式。
## MS UIAutomation (UIA)
MS UIAutomation (以下简称其为 UIA) 是一个 Microsoft 提供的 Framework。用 UIA 可以访问、操作或者监视那些支持 UIA 的控件。
Microsoft 提供的 UI Framework 也基本都支持 UIA 访问(比如: WPF, .NET WinForms, 最基本的 Windows UI 控件 Window, Button, Edit 等)。 

第三方开发的 UI 控件也可以通过实现规定的接口来支持 UIA。本质上 UIA 只是提供了一个 Communication Framework 帮助用户通过 UIA 的 Interface 去访问对应的控件。 

UIA 经常被 QA 用来做为一个 UI Automation Test 的辅助。一些现有的 UI Automation Test Tools 也是基于或部分基于 UIA，比如: MS Coded UI Test, QTP/UFT ( -__-||| )。  

使用 UIA 基本有 2 大块:   
    1. UIA Client: 用户通过 UIA Interface 访问对应 UI 控件。  
    2. UIA Server: Developer 在开发新控件时，为了使新控件支持 UIA 必须实现 UIA 规定的一些接口。  
UIA Client/Server 可以访问 UIA 提供的 .NET, COM Interfaces 。(本文只用到 UIA Client)

## PowerShell 
PowerShell 是 Microsoft 提供的一个 Command-line shell。比起早先的 Windows Console 有相当多的优势 (当然也有一些劣势，比如速度慢了些，使用麻烦了些)。
在这里用到得主要优势是 PowerShell 和 .NET 的整合优势。


## PowerShell + UIA
基本的想法是:    
    1. PowerShell 是一种可以方便访问 .NET Framework 的 Script。   
    2. 并且 PowerShell 是 MS Windows 的一部分。不需要做任何特殊的部署。  
利用 PowerShell 的 Script 去操作 UIA，可以随时修改。也不需要做任何特殊的安装部署。 

基本的使用方法，大致是和在 .NET 中访问 UIA 是一致的。主要区别:需要自己加载 UIAutomation 的 .NET Assemblies 并初始化 Client。  

### Load UIA Assemblies & Startup the client  
以下的 Code snippet 的目的就是用 .NET 的 Reflection 去加载 UIA Assemblies。 
接着把 UIAutomationClientsideProviders 注册到 Client Side 去。*如果不进行注册，会造成无法使用和访问 UIA 的 Patterns。* 
{% highlight ps1 %}
# Load MS UIAutomation assemblies
Write-Host "Loading MS UIA assemblies"
[void][System.Reflection.Assembly]::LoadWithPartialName("UIAutomationClient")
[void][System.Reflection.Assembly]::LoadWithPartialName("UIAutomationTypes")
[void][System.Reflection.Assembly]::LoadWithPartialName("UIAutomationProvider")
[void][System.Reflection.Assembly]::LoadWithPartialName("UIAutomationClientsideProviders")

# Register client side provider
Write-Host "Register client-side provider"
$client = [System.Reflection.Assembly]::LoadWithPartialName("UIAutomationClientsideProviders")
[Windows.Automation.ClientSettings]::RegisterClientSideProviderAssembly($client.GetName())
{% endhighlight %} 

### Sample
下面是一个简单的 Sample。内容也可以在 Gist 上找到：[https://gist.github.com/xiongjia/6749035](https://gist.github.com/xiongjia/6749035) 。  
在这个 Sample 中：  
    1. 用 PowerShell 的 ```Start-Process``` 开启一个 Calc.exe ( Windows 默认计算器 ) 程序。  
    2. 用 Calc.exe 的 process id 找到对应的 Window Element。  
    3. 利用 ClassName 和 Name Properties 查找到 Window 上的 Buttons ('1', '+', '=' 这个 3 个 Buttons)。   
    4. 用 Invoke Pattern 按照顺序 Click 这些 Buttons。   
    5. 最后在 Calc 上应该会得到计算结果 '2'。  

{% gist 6749035 %}

## Misc 
1. 代码重用:   
    PowerShell 提供一些模块化的方式。可以自己扩展 PowerShell 的 cmdlet。随后 Import 到 PowerShell 去。
    (可以参考 Appendix 里提到的书籍 "Windows PowerShell Cookbook")    
2. UI Automation PowerShell Extensions:  
    CodePlex 上有一个开源 PowerShell Extenstion，封装了很多方便的 UIA 方法。[http://uiautomation.codeplex.com/](http://uiautomation.codeplex.com/)    
    我看了一下这个实现，个人不太喜欢的是这个实现基本是 .NET C# 的 Managed code 依赖一些外部的 Assembly。

## Appendix 
1. PowerShell 参考书籍 ["Windows PowerShell Cookbook"](http://book.douban.com/subject/2081681/) 这本书以实例为主。(总体不错，但个人觉得稍微缺乏对 PowerShell 原理解释。)  
2. MS UIAutomation:    
    - MSDN 上的解释比较全面。 目前 Link 是 http://msdn.microsoft.com/en-us/library/ms747327.aspx ，以后可能会变。可以自行在 MSDN 中 Search UIAutomation 来找到对应 Page。   
    - MSDN UIA Blog ，在上面可以找到一些 Sample 和其他文章。不过不经常更新。 http://blogs.msdn.com/b/winuiautomation/   
    - Li Xiong 先生的 Blog 上有多篇解释 UIA 的文章。例如 [UI Automation -- Under the Hood](http://blogs.msdn.com/b/lixiong/archive/2009/12/05/ui-automation-under-the-hood.aspx)   
3. UI Automation Tools:   
    - UISpy, Inspect 这两个是 Microsoft 提供的，也是最常用的。可以用这个 2个工具去查看，操作，监视你要控制的控件。  
      比如我在 Sample 里使用的 ClassName, Name Properties 都是用 UISpy 查看得到的。  
      可以上 MSDN 上 Search UISpy 或 Inspect 来找下载资源，因为 MS 经常改变下载地址。所以我就不贴地址了。
    - UIA Verify 这个一个开源版本的实现。可以达到类似 UI Spy 的功能。具体可以上 CodePlex 上查找相关资源： [http://uiautomationverify.codeplex.com/](http://uiautomationverify.codeplex.com/)   
      UIA Verify 是开源的所以代码本身也是一个良好的 UIA 参考资源。可以从中找到一些 UIA 的使用方法。

