---
layout: post
title: "Azure 中國 SDK&CLI 的使用"
description: ""
category: dev
tags: [dev, azure, tips]
---
{% include JB/setup %}

今周工作主要是把原來 Azure US 的代碼改進至兼容 Azure China 。

大致工作其實也不難， Microsoft 的文檔都有很明確的描述。大概記錄一下幾個點:

----

## Problems

和其他云供應商一樣，要在我朝做生意就要找個代理公司。
並且需要讓其服務受某 "結界" 保護。
並且不能直接和 Azure 的其他 Regions 互通。    
(**注意** Azure China 並不包括香港 region。)

所以 Azure China 的 Account 和幾乎所有對外 REST API 的  URL 都不同于其他 Regions。   
比如: Windows Azure Storage Table Service API 的 DNS Suffix 是 `*.table.core.windows.net`
但在 China Region 則為 `*.table.core.chinacloudapi.cn`

## azure-cli

[Azure CLI](https://www.npmjs.com/package/azure-cli){:target="_blank"} 是一個 Microsoft 
通過 `npm` 的發佈的工具。   
通過該工具可以操控 Azure 輸出的各種 Services。

azure-cli 的安裝使用可以參看 Microsoft 提供的幫助:   

- [Install and Configure the Azure CLI](https://azure.microsoft.com/en-us/documentation/articles/xplat-cli/){:target="_blank"} 

Azure China 需要注意的時，第一次 login 必須增加 `-e AzureChinaCloud` 的參數。
比如:   
{% highlight bash %}
azure login -u [username] -p [password] -e AzureChinaCloud
{% endhighlight %}

Azure China 的文檔中的説明: 

- [如何安装 Azure 跨平台命令行接口](http://www.windowsazure.cn/zh-cn/documentation/articles/xplat-cli/){:target="_blank"} 

## SDK

Azure 有多種 SDK ，目前我用的是和 azure-cli 一樣的 node.js SDK。    
比如:  [Azure Storage SDK](https://github.com/Azure/azure-storage-node){:target="_blank"} 

經由這個 Azure Storage SDK 可以訪問 Azure 的 Storage Services 
(比如: Table Service, Blob Service, File Service )

SDK 同一會在 China Regions 遇到問題，
因爲 Default Settings 裏的 DNS Name 都是爲，Azure US 準備的。
Microsoft 文檔有提到 China Regions 注意事項參考:  

- [Developer Notes for Azure in China Applications](https://msdn.microsoft.com/en-us/library/azure/Dn578439.aspx){:target="_blank"} 

至少有兩种方法可以使其在 China Regions 工作:

1. 改變 "環境變量" ( process environment )     
   增加 `AZURE_STORAGE_DNS_SUFFIX` 環境變量,    
   比如:`set AZURE_STORAGE_DNS_SUFFIX=core.chinacloudapi.cn`     
   如此這樣 Azure node.js SDK 便會從 process.env 去取得 DNS Suffix。  

   此方法雖簡單但缺點十分明顯，即一個 Process 中不能混合操作 China Regions 和其他 Regions。

2. 在 Create Service 時,顯式説明 Host。  
   比如創建針對 China Regions 的 Table Service:    
   (storageAccount & storageAccessKey 可以在自己 Azure Storage Service 設置中找到;
    primaryHost & secondaryHost 是 SDK 也是這麽實現的)
{% highlight js %}
var tableSvc, azureStorage, host, storageAccount, storageAccessKey, url;

azureStorage = require('azure-storage');
url = require('url');

storageAccount = '???';
storageAccessKey = '???';
host = {
  primaryHost: url.format({
    protocol: 'https:',
    host: storageAcc + '.table.core.chinacloudapi.cn' }),
  secondaryHost: url.format({
    protocol: 'https:',
    host: storageAcc + '-secondary.table.core.chinacloudapi.cn' })
};
tableSvc = azureStorage.createTableService(storageAccount,
  storageAccessKey, host);
{% endhighlight %}

----

# 最後

實際在 Azure China Regions 部署服務會遇到更多問題，這些問題也大多與 "結界" 有關。
比如: `npm` 訪問受限，最好切到 [taobao npm mirror](https://npm.taobao.org/){:target="_blank"}。 
其他諸多 package management 都有同樣問題。

