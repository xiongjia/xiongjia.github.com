---
title: md2wechat 测试样本
date:
  created: 2025-09-01
  updated: 2025-09-01
authors: [xiongjia]
tags:
  - test
  - sample
slug: sample
description: >
  md2wechat 功能测试样本，涵盖所有需要转换的语法
categories:
  - bits
  - dev
---

# md2wechat 测试样本

本文件用于测试 `md2wechat` 的所有转换场景。包含语法高亮、admonition、tabs、tasklist、图片引用、脚注、表格、mermaid 等。

<!-- more -->

## 1. 代码语法高亮

### Python

```python
import os
from typing import Optional


def greet(name: str, greeting: Optional[str] = None) -> str:
    """向用户打招呼

    Args:
        name: 用户名
        greeting: 自定义问候语，默认使用 "Hello"

    Returns:
        完整的问候字符串
    """
    msg = greeting or "Hello"
    return f"{msg}, {name}!"


# 使用示例
if __name__ == "__main__":
    print(greet("World"))
    print(greet("Alice", greeting="Hi"))
```

### Bash

```bash
#!/bin/bash
# 发布脚本

set -euo pipefail

PROJECT="xiongjia.github.com"
BRANCH="main"

echo "=== Building $PROJECT ==="
uv run poe build

echo "=== Deploying to gh-pages ==="
mkdocs gh-deploy --force

echo "=== Done ==="
```

### JavaScript

```javascript
/**
 * 格式化日期
 * @param {Date} date
 * @param {string} format - 格式模板，如 'YYYY-MM-DD'
 * @returns {string}
 */
function formatDate(date, format = 'YYYY-MM-DD') {
  const map = {
    YYYY: date.getFullYear(),
    MM: String(date.getMonth() + 1).padStart(2, '0'),
    DD: String(date.getDate()).padStart(2, '0'),
  };
  return format.replace(/YYYY|MM|DD/g, (match) => map[match]);
}

console.log(formatDate(new Date(), 'YYYY/MM/DD'));
// 输出: 2025/09/01
```

### 无语言标识的纯文本代码块

```
echo "纯文本代码块"
echo "没有语法高亮"
```

## 2. 行内代码

在 Python 中可以用 `functools.lru_cache` 实现缓存，使用 `@lru_cache(maxsize=128)` 装饰器。

## 3. Admonition

!!! note "Note 标题"
    这是一个 note 类型的提示框。
    可以包含多行内容。

!!! info
    这是 info 类型，没有自定义标题。

!!! tip
    使用 `uv run poe server` 启动本地开发服务器。

!!! warning
    请勿在生产环境直接使用 draft 模式构建。

!!! danger
    此操作不可逆，请谨慎执行。

## 4. Tabs

=== "pip"
    ```bash
    pip install mkdocs-material
    ```

=== "uv"
    ```bash
    uv add mkdocs-material
    ```

=== "conda"
    ```bash
    conda install -c conda-forge mkdocs-material
    ```

## 5. Tasklist

- [x] 完成核心转换引擎
- [x] 实现代码语法高亮
- [ ] 添加图片自动上传
- [ ] 支持批量转换
- [ ] 集成 AI 辅助改写

## 6. 图片引用

### 本地 WebP 图片

![架构图](./arch.webp)

### 本地 PNG 图片（待转换）

![网络拓扑](./assets/topo.png)

### 远程图片

![示例](https://example.com/sample.jpg)

### 带 title 的图片

![流程图](./flow.webp "系统流程图")

## 7. 脚注

MkDocs 是一个静态站点生成器[^1]，Material for MkDocs 是其最流行的主题[^2]。

[^1]: MkDocs 官方文档：https://www.mkdocs.org/
[^2]: Material for MkDocs：https://squidfunk.github.io/mkdocs-material/

## 8. 表格

| 特性 | MkDocs Material | 微信公众号 | 转换处理 |
|------|-----------------|------------|----------|
| 代码高亮 | ✅ Pygments | ❌ 需内联样式 | Pygments noclasses |
| 外链 | ✅ 可点击 | ❌ 不可点击 | 输出 URL 清单 |
| 本地图片 | ✅ 相对路径 | ❌ 需素材库 | 占位 + 提示上传 |
| Mermaid | ✅ | ❌ | 提示截图 |
| Admonition | ✅ | ❌ | 降级 blockquote |

## 9. Mermaid 图表

```mermaid
flowchart LR
    A[Markdown] --> B[md2wechat]
    B --> C[HTML]
    C --> D[微信公众号]
```

## 10. 链接

- 本站主页：https://xiongjia.github.io
- MkDocs 文档：https://www.mkdocs.org/
- 相对链接：在微信公众号中无法点击，会被收集到检查清单中提示手动处理

## 11. 其他元素

### 定义列表

MkDocs
:   一个快速、简单的静态站点生成器，专注于项目文档。

Material for MkDocs
:   一个基于 Google Material Design 的 MkDocs 主题。

### 缩写

CSS 和 HTML 是 Web 开发的基础技术。

*[CSS]: Cascading Style Sheets
*[HTML]: HyperText Markup Language

### 删除线

~~这段文字已废弃~~，请使用新方案。

### 引用

> 这是普通引用块。
>
> 多行引用。

### 嵌套列表

1. 第一阶段
   - 核心引擎
     - 解析 frontmatter
     - 渲染 HTML
   - 剪贴板集成
2. 第二阶段
   - 微信兼容优化
   - 图片处理
3. 第三阶段
   - Poe 任务集成
   - 交互式选择
