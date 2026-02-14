---
title: SecureJSON 的作用
date:
  created: 2025-09-01
  updated: 2025-09-01
authors: [xiongjia]
tags:
  - general
  - dev
slug: gops
description: >
  SecureJSON 的作用
categories:
  - til
  - dev
---

SecureJSON 这个概念通常指的是一种在 RESTful API 或 Web 服务中，防止 JSON 劫持（JSON Hijacking）攻击的技术。
<!-- more -->

这种攻击方式主要针对一些浏览器行为和 JSON 的特殊性质。攻击者会利用 `<script>` 标签，将你的 API 响应作为 JavaScript 代码加载，从而增加 Web Server 的获取额外的数据并增加额外的负担。   

比如你的 API 返回一个 JSON 结果为一个数组
```json
[
  { "id": 1, "name": "Alice" },
  { "id": 2, "name": "Bob" }
]
```

在 HTML 页面中加入如下代码:
```html
<script src="https://your-api"></script>
```

当浏览器加载这个脚本时，它会执行其中的内容。由于返回的 JSON 可以被解释为有效的 JavaScript 代码。那客户端就可以脚本就可以通过覆盖 Array 的构造函数等方式，劫持并读取你的敏感数据。

---

## SecureJSON 的实现方式

为了防御这种攻击，SecureJSON 技术会在 JSON 响应的开头添加一个非数组和非对象的特殊前缀，让它不再是有效的 JavaScript 代码。
最常见的实现方式是在 JSON 响应的开头加上一个 `while(1);` 或类似的无限循环语句。
```js
while(1);[
  { "id": 1, "name": "Alice" },
  { "id": 2, "name": "Bob" }
]
```

当浏览器尝试将这个响应作为 JavaScript 代码加载时，它会因为 `while(1);` 这个无限循环而卡住，无法继续解析 JSON 数据，从而保护了数据安全。


当你的前端应用通过 fetch 或 XMLHttpRequest 请求这个 API 时，它会接收到完整的响应。然后，你的应用需要手动移除这个前缀，再将剩下的字符串解析为 JSON。
```js
fetch("https://your-api")
  .then(response => response.text())
  .then(text => {
    // 移除 SecureJSON 前缀
    const jsonString = text.substring("while(1);".length);
    const data = JSON.parse(jsonString);
    console.log(data);
  });
```



## 其他

- 不过大多数情况浏览器提供跨域保护，SecureJSON 增加 Server & Client 的负担。不建议启用。
- Gin [:simple-github:](https://github.com/gin-gonic/gin){:target="\_blank"} 有提供对应的 SecureJSON 编码方式。
