# rust-patterns

Learning prototype: runnable Rust patterns, maintained over the long term. This
is my Rust learning path — instead of a phase-by-phase roadmap, each pattern is a
small working example with the reasoning written next to the code (rustdoc doc
comments) and a walkthrough you can actually run.

Started from [Rust Design Patterns](https://rust-unofficial.github.io/patterns/),
and patterns keep being added whenever real code throws the same shape at me
again — not to fill in the book.

## Usage

```bash
cargo run                # list the patterns
cargo run error_enum     # run one pattern's walkthrough

just                     # same as `cargo run`
just run error_enum      # same as `cargo run error_enum`
just test                # unit tests + doc tests
just check               # cargo fmt --check + clippy -D warnings + Markdown/rustdoc check
just check-md            # report unformatted Markdown only
just check-doc           # report rustdoc warnings only (broken or private doc links)
just fmt                 # format everything: Rust, Markdown, the Justfile
just fmt-md              # format Markdown only
just doc                 # rustdoc: the write-ups live in doc comments
```

`cargo run` exit codes: `0` fine, `1` the demo failed, `2` unknown pattern id.

## Patterns

| `id`         | What it shows            |
| ------------ | ------------------------ |
| `error_enum` | Hand-written error enum  |
| `builder`    | Named construction chain |

### `error_enum`

One variant per failure mode, context-carrying fields, and a `Display` that
reads like a sentence:

- **What it shows**: an `Error` enum with a variant per failure mode
  (`Io` / `NotFound` / `KeyTooLarge` / `Corrupt` / `Internal`), context-carrying
  fields (path, key, file id + offset), constructor helpers (`io`, `io_path`,
  `corrupt`) instead of variant literals at the call sites, `Display` wording,
  the `source()` chain a reporter walks, `?` working through
  `From<io::Error>`, and `with_path` to complete a path-less error afterwards
- **Run it**: `cargo run error_enum` (the demo opens a throwaway
  path that cannot exist, so a real `io::Error` shows up, and ends with an
  application-layer `AppError` wrapping the library error — that wrapper is what
  makes the `source()` chain two links long)
- **Source**: [src/patterns/error_enum.rs](./src/patterns/error_enum.rs)
- **Comes from**: [tiny-bitcask](../tiny-bitcask/src/error.rs)'s real `error.rs`,
  simplified (the application-layer `AppError` at the end of the demo is added by
  the walkthrough — the real file has no such wrapper); closest book section:
  [Idiomatic Errors](https://rust-unofficial.github.io/patterns/idioms/ffi/errors.html)

### `builder`

Constructing a type with several (mostly optional) fields, one named value at a
time:

- **What it shows**: a `Command` whose fields are private behind three getters,
  plus the `CommandBuilder` that writes them — `program` / `arg` / `timeout_secs`
  setters that each name one value, take `self` and return `Self`; the defaults
  kept in `Default::default()` as the single source, with `new()` delegating to
  it so the two cannot drift apart; `arg` appending in call order instead of
  making the caller build a `Vec`; and a `build()` that consumes the builder, so
  a half-configured one cannot be reused by mistake
- **Run it**: `cargo run builder` (the walkthrough shows the positional call the
  builder replaces, then the same command as a chain, then what only the builder
  can say — the default it kept and the argument order it preserved)
- **Source**: [src/patterns/builder.rs](./src/patterns/builder.rs)
- **Comes from**: [Builder](https://rust-unofficial.github.io/patterns/patterns/creational/builder.html)
  in Rust Design Patterns; the write-up also covers `&mut self` versus consuming
  `self`, when `build` should return a `Result`, and how `derive_builder`'s
  generated setters differ by default (they borrow with `&mut self` and its
  `build` takes `&self`, so one builder can be built more than once;
  `#[builder(pattern = "owned")]` opts into consuming setters instead). The
  typestate form (required fields encoded in the type, so `build` only exists
  once they are set) is left as a pattern of its own

## Possible next patterns

Candidates for later, picked up when real code asks for them again — **this list
is the living one**. The plan that started this prototype keeps a snapshot, with
the reasoning and the book section for each
([`internal/plans/arch/rust-patterns.md`](../../internal/plans/arch/rust-patterns.md)):

- `coercion-arguments` — `&str` over `&String` in public APIs
- `ctor` / `default` — `new` vs `Default`
- `newtype` — type safety at no cost
- `strategy` — closure vs `dyn` vs a generic parameter
- `raii-guards` / `dtor-finally` — `Drop` cleanup, lock guards
- `visitor` / `command` / `interpreter` — see how they look in Rust
- `fold` — build structures with `Iterator::fold`
- `compose-structs` / `trait-for-bounds` — split fat types, narrow bounds
- `unsafe-mods` — keep `unsafe` in one small module behind a safe API
- `borrow-clone` / `deny-warnings` / `deref-polymorphism` — anti-patterns: ❌ demo + ✅ rewrite
- `typestate` / `sealed-trait` / `extension-trait` — common in real crates
- `phantom-type` / `enum-dispatch` — ZST markers; `enum` + `match` vs `Box<dyn Trait>`
- `cow` / `entry-api` / `parse-dont-validate` — zero-copy, one lookup, validated types
- `interior-mutability` — `Cell` / `RefCell` / `Mutex` boundaries

## Reading the book alongside

- [Rust Design Patterns](https://rust-unofficial.github.io/patterns/) — the
  pattern catalogue this prototype follows
- [The Rust Book](https://doc.rust-lang.org/book/) — language fundamentals
- [Rustlings](https://github.com/rust-lang/rustlings) — exercises
- [The Cargo Book](https://doc.rust-lang.org/cargo/) — build, test, features
- [The rustdoc book](https://doc.rust-lang.org/rustdoc/what-is-rustdoc.html) —
  how the doc comments in each pattern file are rendered

## Status

`experimental` — running it, reading it and testing it all work; the pattern set
keeps growing over time.

Nothing in this repo's CI builds or tests `prototypes/` (by convention), so
`just check` / `just test` are the only guard while working here.
