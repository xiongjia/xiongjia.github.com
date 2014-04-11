---
layout: post
title: "Ractive.js"
description: ""
category: dev
tags: [dev, js]
---
{% include JB/setup %}

最近搞一些服务的后端,由于后端和前端是相互独立存在。
两者之间只能通过后端 server 暴露的 REST API 去访问。

Backend 为了测试方便自己也维护了一个简单的 .html + jQuery 的 AJAX 页面，
来发一些 mock 请求。随着功能越来越多，这个 html 也越來越复杂了。
整个 HTML 的 DOM Tree 在时间的积累下显得越来越零乱。
找机会重构了一下他，在准备时也查看了几其它案:

- AngularJS, 这种做法现下比较流行。也会和我们的 Front End 保持一致。
可缺点是作为一个 Backend 开发我无法短期内充分理解 AngularJS, 他太大;太复杂了 。
- Backbone.js, 这个也不错。从一个非 Front end 的开发来说, Backbone 很容易学习。
而且他的 MVC 也很不错。但是他的 HTML Template 可能不够方便。

相对来说 [Ractive.js](http://www.ractivejs.org/) 的优势: 

- 阅读他的Tutorials , 可能可以在几十钟内初步掌握使用。
- 已经有了我基本需要的几点: HTML Template; 2 way bind; MVC.

我目前没全部看完他手册的打算，列一下我用到的:

 -  [Hello world](http://learn.ractivejs.org/hello-world/)
 -  [List sections](http://learn.ractivejs.org/list-sections/)
 -  [Two-way binding](http://learn.ractivejs.org/two-way-binding/)
 -  [ractive.observe()](http://docs.ractivejs.org/latest/ractive-observe) - 可以用于监视数据改动。
 
