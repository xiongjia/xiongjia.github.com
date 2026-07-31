# prototype-example

Minimal Rust hello-world **example**, used as the first validation of the repo
prototype mechanism: proves that a non-Python toolchain project sits cleanly
under `prototypes/` without disturbing the MkDocs build, ruff / mdformat
formatting, or lint.

> This is an **example**, not a practical prototype — its only purpose is to
> validate the prototype mechanism end-to-end (directory convention, index,
> per-prototype `.gitignore`, fmt/lint skip).

## Usage

```bash
cd prototypes/prototype-example
cargo run                # hello from prototype-example, prototype!
cargo run -- world       # hello from prototype-example, world!
```

## Status

- experimental (mechanism validation example, no real feature)
- Toolchain: Rust (cargo 1.97.0 / rustc 1.97.0), zero external dependencies
