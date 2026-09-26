---
title: Rust Patterns Learning Prototype (rust-patterns)
created: 2026-09-25
archived: 2026-09-26
status: completed
tags: [rust, learning, patterns, prototype]
---

# Rust Patterns Learning Prototype (rust-patterns)

## Goal

**This prototype is my Rust learning path.** Instead of following a
phase-by-phase roadmap, I learn Rust by building small, runnable examples of the
abstractions real code keeps throwing at me, and writing down *why* the code is
written that way. It is maintained over the long term: patterns are added
whenever there is a reason to. The prototype's `README.md` is the entry point for
that path (pattern table + book references), and the current plan covers one of
them in detail.

Scope of this plan: **one pattern** — a **hand-written error type**, a simplified
take on the `Error` enum used in
[`prototypes/tiny-bitcask/src/error.rs`](../../../prototypes/tiny-bitcask/src/error.rs):
variant design, constructor helpers, `Display` wording, `Error::source()`
chaining, `From<io::Error>` for `?`, and a `Result<T>` alias.

Everything else stays in the [Backlog](#backlog-not-scheduled) and is only
added when actually needed.

Current shape (choices, not rules — vary them when a pattern needs it):

- Patterns live under `src/patterns/`, normally one small file with
  implementation, `demo`, doc comments and its `#[cfg(test)]` tests; running one
  goes through the single CLI entry (`cargo run [<id>]`). Bigger patterns may
  spread over files, and the layout may change
- No dependencies so far; a crate that earns its place is fine
- Docs: rustdoc (`cargo doc`) + plain markdown in doc comments — no second doc
  system
- **Self-contained**: the prototype needs nothing from this repo — no vendored
  site assets, no MkDocs, no `internal/` references at build time
- **cargo** + **just**; content is **English** (per the Prototype Convention);
  `edition = "2024"` so the MSRV is 1.85, stated as `rust-version` in `Cargo.toml`

Implementation goes to `prototypes/rust-patterns/` (own `README.md` and
`.gitignore`).

## Design

### Layout

```text
prototypes/rust-patterns/
├── Cargo.toml                # [lib] + [[bin]], no dependencies
├── Cargo.lock                # tracked
├── Justfile                  # 4 recipes: list / run / test / check / doc
├── README.md                 # the learning path: pattern table + book references
├── .gitignore                # /target
└── src/
    ├── main.rs               # THE entry point (~30 lines): list or dispatch by id
    ├── lib.rs                # pub mod demo; pub mod patterns;
    ├── demo.rs               # shared output sink: header, numbered steps, summary
    ├── patterns/
    │   ├── mod.rs            # `mod` list + the PATTERNS table (1 line per pattern)
    │   └── error_enum.rs     # 1 pattern = 1 file: impl + demo + tests + docs
    └── (no examples/, no tests/ dir)
```

`[lib]` + `[[bin]]` rather than bin-only: **doc tests only run for a lib
target** (verified: a binary crate's doc tests are silently skipped by
`cargo test`), and doc tests are exactly what keeps the write-up honest. The
bin stays a thin front door, so there is still only one way to *run* anything.

### The single entry point

```text
cargo run                 -> list every pattern (id + one-liner + status)
cargo run error_enum      -> run that pattern's demo
                              └── demo::run(id, patterns::error_enum::demo)
                                    ├── demo.rs: header, numbered steps, summary
                                    └── exit code 1 on Err, 2 on unknown id
```

- `main.rs` takes **one optional positional argument** (no `clap`, no
  subcommands, no flags); `PATTERNS` is a `&[Pattern]` table (`id`, `summary`,
  `demo` fn) in `src/patterns/mod.rs`
- Each pattern's `demo(&mut Demo)` writes numbered steps and key intermediate
  values; the same function is called by that file's inline tests with a
  string sink, so behavior *and* printed steps are asserted without any CLI
  parsing
- Adding a pattern = **one new file + one table line**

Justfile (kept deliberately small):

```bash
just                   # cargo run            -> list patterns
just run error_enum    # cargo run error_enum  -> run one demo
just test              # cargo test            -> unit tests + doc tests
just check             # cargo fmt --check && cargo clippy --all-targets -- -D warnings
just doc               # cargo doc --no-deps --open
```

**Not chosen for now (reason kept, so it is not relitigated each time):** a
`clap`-based CLI with subcommands; an `examples/<id>.rs` entry per pattern; a
`registry.rs` / `runner.rs` split; a separate `tests/<id>.rs` per pattern. Each
added an entry point (or a dependency) for no gain — `cargo run <id>` plus one
file per pattern covers it.

### What a pattern addition looks like

Roughly one file plus a table row, though the shape may vary:

1. `src/patterns/<id>.rs` — implementation, `pub fn demo(&mut Demo)`, doc
   comments (the write-up), and `#[cfg(test)] mod tests` (behavior + printed
   steps, plus a `compile_fail` doc test when an invariant is worth pinning —
   `error_enum` needed none, since every rule it enforces is a runtime one)
1. one line in the `PATTERNS` table in `src/patterns/mod.rs`
1. a row in the prototype `README.md` pattern table

### Docs (rustdoc only)

- **Doc comments are the single source of truth.** Module-level `//!` gives the
  one-line "what/why"; the defining item (`pub enum Error`, later
  `pub struct Builder`, ...) carries the full write-up in plain markdown:
  headings, prose, code blocks, tables, lists — no diagrams, no extra tooling
- `cargo doc --no-deps --open` (`just doc`) is the only doc command; nothing
  else to install, generate or keep in sync
- `cargo test` runs the doc tests, so every documented example is compiled and
  executed; `cargo test` also builds the bin, so the entry point can never rot
- `README.md` stays the prototype-level entry (learning path + book references);
  when the crate docs want it too, pull it in with
  `#![doc = include_str!("../README.md")]` (decide at M1)

## Tasks

- [x] **M0 — retire the old site-based Rust learning plan** (done 2026-09-25)

  - The roadmap page and its index rows are gone, the Rust-route mention in
    `internal/plans/tauri-ui-research.md` points at this prototype, and the book
    references moved into the prototype `README.md` (M1); nothing about it is
    left on the site

- [x] **M1 — scaffold: one entry point, one working link through the stack** (done 2026-09-25)

  - `cargo new --lib` + `[[bin]]`, **no dependencies**; track `Cargo.lock`
  - `src/demo.rs` (`Demo` sink: header / numbered steps / summary) and
    `src/patterns/mod.rs` (`PATTERNS` table)
  - `src/main.rs`: no arg → list, one arg → dispatch, unknown → exit 2
  - `Justfile` (`default` / `run` / `test` / `fmt` / `fmt-md` / `check` /
    `check-md` / `doc`): `fmt` covers Rust, Markdown (mdformat from the repo venv
    or a standalone `uvx` run) and the Justfile itself; `check` adds clippy on
    all targets (warnings are errors) plus the Markdown and Justfile checks
  - `.gitignore` (`/target`), `Cargo.lock` tracked
  - `README.md` (English): purpose, usage, pattern table (id / what it shows /
    book section link), and the **book references** carried over from the
    deleted learning-plan page ([Rust Design Patterns](https://rust-unofficial.github.io/patterns/),
    [The Rust Book](https://doc.rust-lang.org/book/), [Rustlings](https://github.com/rust-lang/rustlings),
    [Cargo Book](https://doc.rust-lang.org/cargo/)), plus status
  - Acceptance: `just` lists patterns, `just run error_enum` prints a numbered
    walkthrough, `just test` green (unit + doc tests), `just check` clean,
    `just doc` opens the crate docs

- [x] **M2 — the `error_enum` pattern: hand-written error type + Display** (done 2026-09-25)

  - `Error` enum with a small, meaningful variant set, simplified from
    tiny-bitcask: `Io { path: Option<PathBuf>, source: io::Error }`,
    `NotFound { key: String }`, `KeyTooLarge { size, max }`,
    `Corrupt { at: u64, reason: String }`, `Internal(String)`
  - `pub type Result<T> = std::result::Result<T, Error>`
  - Constructor helpers (`Error::io`, `Error::io_path`, `Error::corrupt`) so
    callers never build variant literals by hand
  - `Display`: wording matters — context (path, key, offset) goes into the
    message, no `Debug`-style dumping
  - `std::error::Error::source()` returning the wrapped `io::Error` (so an
    `anyhow`-style reporter can walk the chain)
  - `From<io::Error>` so `?` works on filesystem calls; plus a `with_path`
    context helper (attach a path to a path-less `Io`)
  - `demo(&mut Demo)`: drive a tiny flow that produces every variant, printing
    `Display` for each and walking the `source()` chain
  - Inline tests: exact `Display` strings, `source()` presence (and absence for
    non-wrapping variants), `?` conversion, `with_path`, and the demo steps
  - Doc comments on the `Error` enum: what each variant means, why the
    add-context helpers exist, `Display` vs `Debug` vs `source()`, a comparison
    table (hand-written enum vs `thiserror` vs `anyhow`: what each buys, what it
    costs) and when hand-writing is the right call
  - README row: `error_enum — hand-written error enum, context helpers, Display/source chain`

- [x] **M3 — publish & register the prototype** (done 2026-09-25)

  - `prototypes/README.md`: new entry (Category: `Rust`, status `experimental`,
    later `working` once M2's tests pass; created date; one-line description)
  - `docs/notes/prototypes.md`: sync the index row

## Backlog (not scheduled)

Added **only when a real need shows up**; each entry keeps its book-section
link. Ordering is a suggestion, not a commitment.

| Candidate                                        | Book          | Note                             |
| ------------------------------------------------ | ------------- | -------------------------------- |
| `coercion-arguments` (`&str` over `&String`)     | Idioms        | no `&String` in public APIs      |
| `ctor` / `default`                               | Idioms        | `new` vs `Default`               |
| `newtype`                                        | Behavioural   | type safety at no cost           |
| `builder`                                        | Creational    | optional typestate form          |
| `strategy`                                       | Behavioural   | closure vs `dyn` vs generic      |
| `raii-guards` / `dtor-finally`                   | Behavioural   | `Drop` cleanup, lock guards      |
| `visitor` / `command` / `interpreter`            | Behavioural   | see how they look in Rust        |
| `fold`                                           | Creational    | build with `Iterator::fold`      |
| `compose-structs` / `trait-for-bounds`           | Structural    | split fat types, narrow bounds   |
| `unsafe-mods`                                    | Structural    | keep `unsafe` in a small module  |
| `borrow-clone` / `deny-warnings`                 | Anti-patterns | ❌ demo + ✅ rewrite             |
| `deref-polymorphism`                             | Anti-patterns | `Deref` as fake inheritance      |
| `typestate` / `sealed-trait` / `extension-trait` | Ecosystem     | common in real crates            |
| `phantom-type` / `enum-dispatch`                 | Ecosystem     | ZST markers; enum vs `dyn`       |
| `cow` / `entry-api` / `parse-dont-validate`      | Ecosystem     | zero-copy, one lookup, validated |
| `interior-mutability`                            | Ecosystem     | `Cell` / `RefCell` / `Mutex`     |

Explicitly deferred: any macro-crate comparison in code (`derive_builder`,
`strum`, `thiserror` stay doc-only mentions).

## Notes

- **Language**: English everywhere inside the prototype (README, doc comments)
  per the Prototype Convention
- **Dependencies**: none. `thiserror` / `anyhow` are *discussed* in the
  error-enum write-up, not depended on — the point is to write and understand
  the impl by hand first
- **No repo coupling at build/run time**: the prototype needs nothing from this
  repo (no vendored site assets, no MkDocs, no `internal/` references in code or
  docs). Only the Markdown tooling prefers the repo's uv environment and falls
  back to a standalone `uvx` run when the prototype is copied elsewhere
- **Naming**: module `snake_case` (`src/patterns/error_enum.rs`), CLI id
  `kebab-case` or snake_case as typed in the table — ids are stable once added
- **Demos are explanations**: numbered steps plus key intermediate values, so
  running the demo is itself the note
- **The learning path lives in the prototype README** (pattern table + book
  references); prototypes are deliberately outside the MkDocs build
- **Relation to tiny-bitcask**: that prototype shows the error enum inside a
  real I/O engine; this one isolates the design decisions. The simplification is
  intentional (fewer variants, no async/tokio variants) and the write-up should
  list what was dropped and why
- **Long-term maintenance**: the backlog table is the parking lot; a row moves
  into `Tasks` when it is picked up, and adding it = the one-file DoD above
- Requires developer approval before execution; no branch switching

## Status

- **M0/M1/M2/M3 done** (2026-09-25): `prototypes/rust-patterns/` exists with the
  single entry point, the `error_enum` pattern, 18 unit tests + 3 doc tests
  (`just test`) and `just check` clean, and the prototype is registered in
  `prototypes/README.md` and `docs/notes/prototypes.md`
- `just fmt` / `just check` also cover Markdown and the Justfile; the demo opens
  a path it never creates (asserted in the test) so it cannot depend on the
  environment; no `compile_fail` doc test was needed
- **Archived 2026-09-26 as completed**: the initial plan is done (prototype
  scaffolded, first pattern in place, registered, committed). The prototype is
  maintained over the long term; the backlog table above is the snapshot this
  plan started from, and the living candidate list is in the prototype README
  (`prototypes/rust-patterns/README.md`). A candidate that grows past a one-file
  change gets its own plan
- Later (2026-09-26): the demo sink moved to `&Demo` + `Cell`/`RefCell`, so
  `DemoFn` is `fn(&Demo) -> DemoResult` and no caller needs a `mut` binding. The
  `demo(&mut Demo)` mentions in the body above describe the design as it stood
  when this plan was completed

## References

- [Rust Design Patterns](https://rust-unofficial.github.io/patterns/)
  ([Idiomatic Errors](https://rust-unofficial.github.io/patterns/idioms/ffi/errors.html)
  is the closest book section) — linked from the prototype `README.md`, not from
  the site
- [tiny-bitcask error.rs](../../../prototypes/tiny-bitcask/src/error.rs) — where
  the `error_enum` pattern comes from
- [The rustdoc book](https://doc.rust-lang.org/rustdoc/what-is-rustdoc.html) ·
  [`std::error::Error`](https://doc.rust-lang.org/std/error/trait.Error.html)
- [thiserror](https://docs.rs/thiserror) · [anyhow](https://docs.rs/anyhow)
  (comparison only, in the write-up)
