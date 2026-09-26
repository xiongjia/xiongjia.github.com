//! Learning prototype: runnable Rust patterns, maintained over the long term.
//!
//! Each pattern lives under [`patterns`] — implementation, a `demo` walkthrough,
//! its tests and the write-up in doc comments, usually all in one file. The
//! binary ([`main`](../../main.rs)) lists the patterns or runs one of them.
//!
//! The crate is split into a library + a binary so that `cargo test` runs the doc
//! tests (they only run for a lib target), and the doc tests are what keep the
//! write-ups honest: every documented example has to compile and run.
#![warn(missing_docs)]

pub mod demo;
pub mod patterns;
