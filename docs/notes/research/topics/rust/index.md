---
hide:
  - navigation
title: Rust 学习计划
tags:
  - research
  - tech
categories:
  - dev
---

# Rust 学习计划

## 为什么学 Rust

- **零成本抽象** — 高级语言的表达能力，C 级别的性能
- **内存安全** — 编译期所有权系统消除 segfault / use-after-free / data race
- **生态成熟** — 包管理器 Cargo、crates.io、一流工具链
- **适用场景** — 系统编程、WebAssembly、CLI 工具、网络服务、嵌入式

## 学习资源

### 必读

| 资源                                                          | 说明                  |
| ------------------------------------------------------------- | --------------------- |
| [The Rust Book](https://doc.rust-lang.org/book/)              | 官方入门书，必读      |
| [Rust by Example](https://doc.rust-lang.org/rust-by-example/) | 示例驱动的学习        |
| [Rustlings](https://github.com/rust-lang/rustlings)           | 交互式练习 (强烈推荐) |
| [The Cargo Book](https://doc.rust-lang.org/cargo/)            | 构建系统和包管理      |
| [Rust Standard Library](https://doc.rust-lang.org/std/)       | 标准库文档            |

### 进阶

| 资源                                                                | 说明             |
| ------------------------------------------------------------------- | ---------------- |
| [The Rustonomicon](https://doc.rust-lang.org/nomicon/)              | unsafe Rust 深入 |
| [Rust Reference](https://doc.rust-lang.org/reference/)              | 语言规范         |
| [Async Book](https://rust-lang.github.io/async-book/)               | 异步编程         |
| [Rust Cookbook](https://rust-lang-nursery.github.io/rust-cookbook/) | 常用模式速查     |

### 工具链

```bash
# 安装 Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 更新
rustup update

# 查看版本
rustc --version
cargo --version
```

## 学习阶段

### 阶段 1: 基础语法 (Week 1-2)

**目标**: 能看懂 Rust 代码，写简单程序

1. **环境搭建**

   - 安装 rustup、配置编辑器 (VS Code + rust-analyzer)
   - 运行 `cargo new hello` 创建第一个项目

1. **基础语法**

   - 变量绑定 (`let`、`let mut`)、类型推断
   - 基本类型: `i32`、`u64`、`f64`、`bool`、`char`、`&str`、`String`
   - 函数、控制流 (`if`、`loop`、`while`、`for`)
   - `match` 模式匹配
   - 复合类型: `struct`、`enum`、`tuple`、`Vec`、`HashMap`

1. **练习**

   - 完成 [Rustlings](https://github.com/rust-lang/rustlings) 的 `variables` ~ `structs` 部分

### 阶段 2: 核心概念 — 所有权 (Week 3-4)

**目标**: 理解 Rust 最核心的机制

> ⚠️ 这是 Rust 最大的学习瓶颈，必须花时间理解

4. **所有权 (Ownership)**

   - 所有权规则 (一个值只有一个 owner)
   - `move` vs `clone` vs `copy`
   - 借用 (`&T`) 与可变借用 (`&mut T`)
   - 引用规则 (多个只读引用 XOR 一个可变引用)

1. **生命周期 (Lifetime)**

   - 为什么需要生命周期标注
   - `'a` 语法、生命周期省略规则
   - 结构体中的生命周期
   - 常见生命周期错误及修复

1. **练习**

   - 完成 Rustlings 的 `move_semantics` ~ `lifetimes`
   - 手写一个简单的链表 (不用 `std::collections`)

### 阶段 3: 错误处理与泛型 (Week 5-6)

7. **错误处理**

   - `panic!` vs `Result<T, E>`
   - `?` 操作符
   - `Option<T>` 处理空值
   - 自定义错误类型 (`thiserror` + `anyhow`)
   - `unwrap()` / `expect()` 的使用场景

1. **泛型与 Trait**

   - 泛型函数 / 泛型 struct
   - Trait 定义与实现
   - `impl Trait` vs `dyn Trait`
   - `derive` 宏
   - 常用 std trait: `Clone`、`Copy`、`Debug`、`Display`、`PartialEq`、`Default`

1. **练习**

   - 用泛型和 trait 实现一个简单的数学库

### 阶段 4: 常用集合与迭代器 (Week 7)

10. **集合**

    - `Vec<T>` — 动态数组
    - `HashMap<K, V>` — 哈希表
    - `String` — 字符串处理 (注意 UTF-8)
    - `VecDeque<T>` — 双端队列
    - `BTreeMap<K, V>` — 有序映射

01. **迭代器**

    - `Iterator` trait
    - `iter()` / `iter_mut()` / `into_iter()`
    - 组合子: `map`、`filter`、`fold`、`collect`、`flat_map`
    - 惰性求值、零开销抽象

### 阶段 5: 模块化与包管理 (Week 8)

12. **模块系统**

    - `mod`、`use`、`pub`
    - 项目结构: `src/main.rs` vs `src/lib.rs`
    - 模块树 vs 文件树
    - `use` 路径习惯

01. **Cargo 深入**

    - `Cargo.toml` 依赖管理
    - `cargo build` / `cargo test` / `cargo run`
    - `cargo doc --open`
    - `cargo clippy` (代码检查)
    - `cargo fmt` (代码格式化)
    - feature flags
    - workspace 管理多 crate 项目

### 阶段 6: 并发与异步 (Week 9-10)

14. **线程**

    - `std::thread::spawn`
    - `Send` / `Sync` trait (线程安全标记)
    - `Mutex<T>` / `RwLock<T>`
    - `Arc<T>` — 线程安全的引用计数
    - `mpsc::channel` — 消息传递

01. **异步 (Async/Await)**

    - `async fn` 和 `.await`
    - `tokio` 运行时
    - `tokio::spawn` / `tokio::select!`
    - async trait (1.75+)
    - `futures` crate 常用工具

### 阶段 7: 实战项目 (Week 11+)

16. **CLI 工具**

    - `clap` — 命令行参数解析
    - `indicatif` — 进度条
    - `anyhow` — 错误处理

01. **Web 服务**

    - `axum` / `actix-web` — HTTP 框架
    - `sqlx` — 异步数据库
    - `serde` / `serde_json` — 序列化
    - `tokio` — 异步运行时

01. **FFI / 调用 C 库**

## 关键概念速查

| 概念                 | 一句话解释                                  |
| -------------------- | ------------------------------------------- |
| **Ownership**        | 每个值只有一个 owner，离开作用域自动释放    |
| **Borrowing**        | 引用某个值但不获取所有权                    |
| **Lifetime**         | 编译器保证引用不会比被引用值活得更久        |
| **Move**             | 所有权转移，原变量失效                      |
| **Clone**            | 显式复制（深拷贝）                          |
| **Copy**             | 隐式复制（栈上简单类型）                    |
| **Trait**            | 类似 Go 的 interface 或 Java 的 interface   |
| **Enum**             | 带数据的枚举 (sum type)，比 C enum 强大多了 |
| **Pattern Matching** | `match` 穷举所有分支，编译器检查            |
| **Send**             | 类型可以安全地跨线程传递所有权              |
| **Sync**             | 类型可以安全地跨线程共享引用                |

## 常用 Crate

| Crate                  | 用途            |
| ---------------------- | --------------- |
| `serde` / `serde_json` | 序列化/反序列化 |
| `tokio`                | 异步运行时      |
| `axum` / `actix-web`   | HTTP 框架       |
| `sqlx` / `diesel`      | 数据库          |
| `clap`                 | CLI 参数解析    |
| `thiserror` / `anyhow` | 错误处理        |
| `reqwest`              | HTTP 客户端     |
| `tracing`              | 结构化日志      |
| `rayon`                | 数据并行        |
| `clap`                 | CLI 构建        |

## 常见错误与陷阱

| 问题                                        | 解决方法                                     |
| ------------------------------------------- | -------------------------------------------- |
| `cannot move out of borrowed content`       | 用 `clone()` 或改变设计                      |
| `does not live long enough`                 | 调整生命周期或使用 `Arc`                     |
| `cannot borrow X as mutable more than once` | 缩小借用范围或重构                           |
| `the trait bound X: Clone is not satisfied` | 添加 `#[derive(Clone)]` 或实现 `Clone`       |
| `string vs &str` 混淆                       | `&str` 是借用，`String` 是拥有所有权的字符串 |
| 循环引用导致内存泄漏                        | 用 `Weak<T>` 打破循环                        |

## 学习建议

1. **不要跳过所有权** — 这是 Rust 的核心，卡住是正常的
1. **用 Rustlings 练习** — 比被动看书效率高很多
1. **写代码 > 看书** — 每天写至少 50 行 Rust
1. **读懂编译器错误** — Rust 的错误信息是最好的老师
1. **从 CLI 工具入手** — 比 Web 项目简单，更容易上手
1. **不要过早接触 unsafe** — 99% 的代码不需要它
1. **用 clippy** — `cargo clippy` 教你的不仅是 lint，还有惯用法
