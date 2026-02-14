---
title: PDM 设置
date:
  created: 2025-08-09
  updated: 2025-08-09
authors: [xiongjia]
tags:
  - py
  - dev
slug: pdm-config
description: >
  PDM 设置
categories:
  - til
  - dev
---

PDM 的镜像设置和其他配置

<!-- more -->

### 常用配置

设置 pdm cache 目录的位置 (修改配置文件的方式，以后长期有效)

```bash
# 查看当前配置
pdm config
# 设置新缓存路径
pdm config cache_dir "/new/cache/path"
# 验证 (查看是否设置成功)
pdm config cache_dir
```

设置 pdm cache 目录的位置 (通过环境变量临时修改)

=== "Unix Shell"
    ```bash
    # 在 Unix OS
    export PDM_CACHE_DIR="/new/cache/path"
    pdm install
    ```
=== "Windows PowerShell"
    ```bash
    # 在 Windows PowerShell 上
    $env:PDM_CACHE_DIR = "D:\new\cache\path"
    pdm install
    ```

### 镜像设置

设置 pypi 镜像站点。可以选择

- 腾讯云的镜像: [https://mirrors.cloud.tencent.com/](https://mirrors.cloud.tencent.com/){:target="\_blank"}
- 阿里云的镜像: [https://developer.aliyun.com/mirror/](https://mirrors.cloud.tencent.com/){:target="\_blank"}


设置对应的 pypi 

```bash
# 查看当前配置
pdm config
# 设置 阿里云 pypi 
pdm config pypi.url https://mirrors.aliyun.com/pypi/simple
# 设置 腾讯 pypi 
pdm config pypi.url https://mirrors.cloud.tencent.com/pypi/simple

# 如果只为当前工程设置可以加上 -l 参数。
# 这样 pdm 会生成一个配置文件在 pdm 工程目录，该设置只影响当前工程。
# 比如 为当前工程设置 pypi.url 到腾讯
# (建议不做此设置，因为可能会影响 CI 环境和别的开发的环境)
pdm config -l pypi.url https://mirrors.cloud.tencent.com/pypi/simple
```

???+ info "note"
    阿里云、腾讯 或者其他镜像。地址和设置方式可能会在以后改变，设置前检查对应镜像网站的设置说明。


### package 安装设置

启用以下设置后 PDM 会把对应的 python packages 装在对应的工程目录里的 `__pypackages__` 。
这个做法可以避免污染 venv 里的 python 环境，不过会导致占用更多磁盘空间。

```bash
# 查看当前配置
pdm config
# 设置禁用 use_venv 
pdm config global_project.fallback false
pdm config python.use_venv false
# 验证 (查看是否设置成功)
pdm config global_project.fallback
pdm config python.use_venv
```

---


???+ info "appendix"
    - PDM 文档: [https://pdm-project.org/](https://pdm-project.org/){:target="\_blank"}
    - PDM Config 说明书: [https://pdm-project.org/latest/usage/config/](https://pdm-project.org/){:target="\_blank"}

