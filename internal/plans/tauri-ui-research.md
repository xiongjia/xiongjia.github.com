---
title: Tauri UI Research (Desktop & Mobile)
created: 2026-08-17
tags: [tauri, desktop, mobile, rust, research, prototype]
---

# Tauri UI Research (Desktop & Mobile)

## Goal

学习 Tauri 框架做桌面端（Tauri 2）与移动端（iOS/Android）应用：
架构原理（Rust core + WebView 前端）、IPC、插件体系、打包分发，
评估与本项目 Rust 学习路线（`docs/notes/research/topics/rust/`）的衔接。

产出形式：research 笔记或 prototype。内容落在
`docs/notes/research/topics/tauri/`；原型放 `prototypes/tauri-app/`。

## Tasks

- [ ] **Research: Tauri 架构与核心概念**

  - Tauri 2 架构：Rust 后端 + 系统 WebView（WKWebView/WebView2/WebKitGTK）
  - 与 Electron 的对比（体积、内存、安全模型）
  - 核心 crate：tauri、tauri-build、tauri-plugin-\*
  - 发布到 `docs/notes/research/topics/tauri/`

- [ ] **Research: IPC 与前端集成**

  - `invoke` / events（emit/listen）通信模型
  - 前端框架选择（React/Vue/Svelte）与 Vite 集成
  - capabilities/permissions 安全配置
  - 发布到 `docs/notes/research/topics/tauri/`

- [ ] **Research: 移动端支持（Tauri Mobile）**

  - iOS/Android 支持现状与限制（WebView 差异、插件适配）
  - 移动端打包：`tauri android` / `tauri ios`、签名与分发
  - 桌面 ↔ 移动的代码复用策略
  - 发布到 `docs/notes/research/topics/tauri/`

- [ ] **Prototype（可选）: 最小应用验证**

  - `create-tauri-app` 建桌面 demo，验证 IPC + 前端构建
  - 若环境允许，跑一次移动端 build 验证可行性
  - 原型放在 `prototypes/tauri-app/`（含独立 README + .gitignore）

- [ ] **总结**

  - 更新 `docs/notes/research/index.md` 表格
  - 与本项目 Rust 学习路线衔接：哪些 tauri 源码部分值得继续深入

## Notes

- 移动端仍需 Rust 移动工具链（iOS 需 Xcode、Android 需 Android SDK），如本机不具备可先只做桌面验证
- Tauri 2 为当前稳定大版本，以它为准

## References

- [Collection: Dev Tools](../../docs/notes/collection/dev-tools.md)
- [Tauri 官方文档](https://v2.tauri.app/)
