//! Hand-written error enum.
//!
//! The pattern: instead of reaching for a crate, write the error type by hand —
//! one enum per module, one variant per failure mode, constructor helpers that
//! keep the variant fields out of the call sites, a `Display` that reads like a
//! sentence and a `source()` that keeps the wrapped cause reachable.
//!
//! Run `cargo run error_enum` to watch every variant print itself; the
//! reasoning lives on [`Error`], and `#[cfg(test)] mod tests` at the bottom of
//! this file pins the behaviour (exact messages, where `source()` exists, how
//! `?` converts).

use std::error::Error as StdError;
use std::fmt;
use std::fs::File;
use std::io;
use std::path::{Path, PathBuf};

use crate::demo::{Demo, DemoResult};

/// Convenience alias: every fallible function in this module returns this.
///
/// Writing `Result<T>` instead of `std::result::Result<T, Error>` at every call
/// site is the same trick as `std::io::Result<T>`: the error type of a module
/// is part of its interface, so give it a short name and use it everywhere.
pub type Result<T> = std::result::Result<T, Error>;

/// Every way this module can fail.
///
/// # Why one enum instead of a crate
///
/// | Approach | What it buys | What it costs |
/// | --- | --- | --- |
/// | Hand-written enum (this) | Callers can match on the failure mode; no dependency; the compiler forces you to add a `Display` arm for every variant | Boilerplate per variant, and it grows with the module |
/// | `thiserror` | The same enum with `Display`/`source`/`From` derived from attributes | One dependency (plus a proc-macro at build time); the generated impls are invisible in the source |
/// | `anyhow` | `anyhow::Error` for whole applications, easy `context()` stacking | Callers can no longer match on the failure mode; only good at the top of an application, never in a library API |
///
/// Rule of thumb: **a library defines an enum, an application's `main` may use
/// `anyhow`.** This module is the library case (a storage engine), so the enum
/// is written by hand — which is also the only way to actually learn what
/// `thiserror` generates.
///
/// # What every variant carries
///
/// The variants exist to tell three very different situations apart:
///
/// - **bad input** ([`Error::NotFound`], [`Error::KeyTooLarge`]) — the caller's
///   fault; the fields keep the rejected numbers so the message can be specific
/// - **damaged or inaccessible data** ([`Error::Corrupt`], [`Error::Io`]) — the
///   environment's fault; these carry *where* it happened (file id, offset, path)
/// - **a bug** ([`Error::Internal`]) — an invariant that should be impossible;
///   worth its own variant so it never gets confused with the two above
///
/// # `Display`, `Debug` and `source()`
///
/// - [`fmt::Display`] is the message for humans: one sentence, with context
///   inlined (`io error on /data/rust-patterns/000001.data: No such file or
///   directory`). No
///   `Debug`-style dumping, no trailing colon.
/// - [`Debug`] is derived: it shows the variant and every field, which is right
///   for tests and logs but wrong for a user-facing message.
/// - [`StdError::source`] exposes the wrapped cause (`io::Error`) so a reporter
///   at the top of the program can print the whole chain instead of just the
///   outermost layer.
///
/// ```
/// use rust_patterns::patterns::error_enum::{Error, Result};
///
/// fn read(path: &str) -> Result<String> {
///     // `?` works because of `impl From<io::Error> for Error` below.
///     let text = std::fs::read_to_string(path)?;
///     Ok(text)
/// }
///
/// let err = match read("/rust-patterns/definitely-missing") {
///     Ok(_) => Error::Internal("the probe file should not exist".to_string()),
///     Err(err) => err,
/// };
/// // The message is a sentence, and the io error is still reachable.
/// assert!(err.to_string().starts_with("io error: "));
/// ```
#[derive(Debug)]
pub enum Error {
    /// An I/O call failed.
    ///
    /// `path` is `None` when the error came from a `?` conversion and the call
    /// site did not know (or bother with) the path; [`Error::with_path`] fills
    /// it in later.
    Io {
        /// The file the operation was about, when it is known.
        path: Option<PathBuf>,
        /// The original error, kept for [`StdError::source`].
        source: io::Error,
    },
    /// Something was looked up and is not there.
    NotFound {
        /// The lookup key, kept for the message.
        key: String,
    },
    /// A key is longer than the on-disk field can express.
    KeyTooLarge {
        /// Size of the rejected key, in bytes.
        size: usize,
        /// Largest key this format can store.
        max: usize,
    },
    /// A record could not be decoded.
    Corrupt {
        /// The data file the record lives in.
        file_id: u32,
        /// Byte offset of the record inside that file.
        offset: u64,
        /// What exactly was wrong, in words.
        reason: String,
    },
    /// An invariant or hard limit was hit: a bug, never bad input.
    Internal(String),
}

impl Error {
    /// Wrap an [`io::Error`] when the operation has no path to attach.
    ///
    /// Used by the [`From`] impl below, but public because `?` is not always the
    /// way an error arrives (for example inside a `match`).
    #[must_use]
    pub fn io(source: io::Error) -> Self {
        Self::Io { path: None, source }
    }

    /// Wrap an [`io::Error`] together with the path it happened on.
    ///
    /// Prefer this (or [`Error::with_path`]) over [`Error::io`]: a path turns
    /// `io error: Permission denied` into
    /// `io error on /data/rust-patterns/000001.data: Permission denied`, which is the difference between a bug report and a
    /// guessing game.
    #[must_use]
    pub fn io_path(path: impl AsRef<Path>, source: io::Error) -> Self {
        Self::Io {
            path: Some(path.as_ref().to_path_buf()),
            source,
        }
    }

    /// Build an [`Error::Corrupt`] with a human-readable reason.
    ///
    /// A constructor keeps the call sites short (`Error::corrupt(id, offset,
    /// "crc32 mismatch")`) and leaves room to add fields later without touching
    /// every call site.
    #[must_use]
    pub fn corrupt(file_id: u32, offset: u64, reason: impl Into<String>) -> Self {
        Self::Corrupt {
            file_id,
            offset,
            reason: reason.into(),
        }
    }

    /// Attach a path to a path-less [`Error::Io`].
    ///
    /// Every other variant — including an `Io` that already knows its path — is
    /// returned unchanged, so it is safe to use as a catch-all context fixup:
    ///
    /// ```
    /// # use rust_patterns::patterns::error_enum::Error;
    /// let err = Error::io(std::io::Error::from(std::io::ErrorKind::NotFound))
    ///     .with_path("/data/rust-patterns/000001.data");
    /// // The message is a sentence; the exact io wording belongs to std.
    /// assert!(err.to_string().starts_with("io error on /data/rust-patterns/000001.data: "));
    /// ```
    #[must_use]
    pub fn with_path(self, path: impl AsRef<Path>) -> Self {
        match self {
            Self::Io { path: None, source } => Self::Io {
                path: Some(path.as_ref().to_path_buf()),
                source,
            },
            other => other,
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io {
                path: Some(path),
                source,
            } => write!(f, "io error on {}: {source}", path.display()),
            Self::Io { path: None, source } => write!(f, "io error: {source}"),
            Self::NotFound { key } => write!(f, "key {key:?} was not found"),
            Self::KeyTooLarge { size, max } => {
                write!(f, "key is {size} bytes, the limit is {max} bytes")
            }
            Self::Corrupt {
                file_id,
                offset,
                reason,
            } => write!(
                f,
                "corrupt record in file {file_id} at offset {offset}: {reason}"
            ),
            Self::Internal(message) => write!(f, "internal error: {message}"),
        }
    }
}

impl StdError for Error {
    /// Only the variants that wrap another error have a source; the rest are
    /// the end of the chain, and returning `None` there is what makes a
    /// reporter stop instead of looping.
    fn source(&self) -> Option<&(dyn StdError + 'static)> {
        match self {
            Self::Io { source, .. } => Some(source),
            _ => None,
        }
    }
}

impl From<io::Error> for Error {
    /// This one impl is what makes `?` work on every filesystem call.
    fn from(source: io::Error) -> Self {
        Self::io(source)
    }
}

/// Open the file a record lives in, letting `?` do the conversion.
///
/// Note what is *missing*: no `map_err`. `?` calls [`From::from`], which builds
/// a path-less [`Error::Io`]. The caller can still add context afterwards with
/// [`Error::with_path`] (see the demo) — or map at the call site, like
/// [`open_file_at`] does. (Opening, rather than reading, keeps the example
/// honest: the point here is the error, not what the file contains.)
fn open_file(path: &Path) -> Result<File> {
    let file = File::open(path)?;
    Ok(file)
}

/// Open a file, attaching the path at the call site.
///
/// Versus [`open_file`]: the context is attached where it is known, so the error
/// is complete the moment it is created. This is the style to prefer;
/// `?` + [`Error::with_path`] is the fallback for the cases where the path only
/// becomes known further up.
fn open_file_at(path: &Path) -> Result<File> {
    let file = File::open(path).map_err(|source| Error::io_path(path, source))?;
    Ok(file)
}

/// Printed when the probe path does exist after all — impossible by
/// construction, but the demo says so instead of pretending to fail.
const UNEXPECTED_PROBE_EXISTS: &str = "unexpected: the probe path exists after all";

/// Walk through every variant: what it means, its `Display`, its `Debug`, and
/// its `source()` chain.
///
/// # Errors
///
/// Never: the failing calls below are the point of the demo, and each one is
/// reported instead of propagated.
pub fn demo(sink: &Demo) -> DemoResult {
    let missing = missing_path();
    sink.step("Bad input is the caller's fault: the variant carries the rejected values");
    report(
        sink,
        &Error::KeyTooLarge {
            size: 300,
            max: 255,
        },
    );
    report(
        sink,
        &Error::NotFound {
            key: "user:42".to_string(),
        },
    );

    sink.step("Damaged data is the environment's fault: the variant carries where it was seen");
    report(sink, &Error::corrupt(3, 4096, "crc32 mismatch"));

    sink.step("`?` turns an io::Error into our Error, but has no path to attach");
    report_open(sink, open_file(&missing));

    sink.step("The caller knows the path, so `with_path` completes the error afterwards");
    report_open(
        sink,
        open_file(&missing).map_err(|err| err.with_path(&missing)),
    );

    sink.step("Mapping at the call site does the same thing in one step");
    report_open(sink, open_file_at(&missing));

    sink.step("An impossible invariant gets its own variant, never confused with the above");
    report(
        sink,
        &Error::Internal("file id space exhausted".to_string()),
    );

    sink.step("What to remember when writing the next error type");
    sink.detail("Display  is one sentence for humans (see every line above)");
    sink.detail("Debug    is derived, for tests and logs, and shows every field");
    sink.detail("source() is what a reporter walks to print the whole cause chain");
    Ok(())
}

/// A path the demo never creates, so opening it produces a real `io::Error`.
///
/// Relative, and scoped by process id: nothing here ever creates it (the demo
/// only opens), and `demo_walks_every_variant` asserts it is absent before
/// running, so the walkthrough cannot quietly depend on the environment. A
/// fixed absolute path such as `/data/...` would depend on what happens to
/// exist on the machine, and a temp-directory path would bury the one thing the
/// demo is printing — the message.
fn missing_path() -> PathBuf {
    PathBuf::from(format!("rust-patterns-missing-{}", std::process::id())).join("000001.data")
}

/// Print the outcome of one of the demo's opening attempts.
///
/// The three call sites differ only in *how* they get their error (bare `?`,
/// `with_path` afterwards, mapping at the call site), so the printing lives
/// here once.
fn report_open(sink: &Demo, opened: Result<File>) {
    match opened {
        Ok(_) => sink.detail(UNEXPECTED_PROBE_EXISTS),
        Err(err) => report(sink, &err),
    }
}

/// Print one error three ways, so the difference is visible side by side.
fn report(sink: &Demo, err: &Error) {
    sink.detail(format!("Display : {err}"));
    sink.detail(format!("Debug   : {err:?}"));
    sink.detail(format!("source  : {}", source_chain(err)));
}

/// Flatten an error's `source()` chain into one line, or `(none)`.
fn source_chain(err: &dyn StdError) -> String {
    let mut causes = Vec::new();
    let mut current = err.source();
    while let Some(cause) = current {
        causes.push(cause.to_string());
        current = cause.source();
    }
    if causes.is_empty() {
        "(none)".to_string()
    } else {
        causes.join(" -> ")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display_carries_the_context_of_each_variant() {
        assert_eq!(
            Error::NotFound {
                key: "user:42".into()
            }
            .to_string(),
            "key \"user:42\" was not found"
        );
        assert_eq!(
            Error::KeyTooLarge {
                size: 300,
                max: 255
            }
            .to_string(),
            "key is 300 bytes, the limit is 255 bytes"
        );
        assert_eq!(
            Error::corrupt(3, 4096, "crc32 mismatch").to_string(),
            "corrupt record in file 3 at offset 4096: crc32 mismatch"
        );
        assert_eq!(
            Error::Internal("file id space exhausted".into()).to_string(),
            "internal error: file id space exhausted"
        );
    }

    #[test]
    fn only_wrapping_variants_have_a_source() {
        let io_error = Error::io(io::Error::from(io::ErrorKind::PermissionDenied));
        assert!(io_error.source().is_some(), "Io wraps an io::Error");

        for err in [
            Error::NotFound { key: "k".into() },
            Error::KeyTooLarge { size: 1, max: 0 },
            Error::corrupt(1, 0, "bad"),
            Error::Internal("boom".into()),
        ] {
            assert!(
                err.source().is_none(),
                "{err:?} is the end of the chain, so source() must be None"
            );
        }
    }

    #[test]
    fn question_mark_converts_without_attaching_a_path() {
        let err = open_file(&missing_path()).expect_err("the probe path does not exist");
        assert!(
            matches!(err, Error::Io { path: None, .. }),
            "? goes through From<io::Error> and knows no path, got {err:?}"
        );
    }

    #[test]
    fn with_path_completes_a_path_less_io_error() {
        let probe = missing_path();
        let err = open_file(&probe)
            .map_err(|err| err.with_path(&probe))
            .expect_err("the probe path does not exist");
        assert!(
            matches!(&err, Error::Io { path: Some(path), .. } if path == &probe),
            "with_path must attach the path, got {err:?}"
        );
        assert!(
            err.to_string()
                .starts_with(&format!("io error on {}: ", probe.display()))
        );
    }

    #[test]
    fn with_path_leaves_every_other_variant_alone() {
        let probe = missing_path();
        let original = Error::corrupt(1, 2, "bad crc");
        let expected = original.to_string();
        assert_eq!(original.with_path(&probe).to_string(), expected);

        let already_pathed = Error::io_path(&probe, io::Error::from(io::ErrorKind::NotFound));
        let expected = already_pathed.to_string();
        assert_eq!(already_pathed.with_path("elsewhere").to_string(), expected);
    }

    #[test]
    fn mapping_at_the_call_site_keeps_the_path() {
        let probe = missing_path();
        let err = open_file_at(&probe).expect_err("the probe path does not exist");
        assert!(
            matches!(&err, Error::Io { path: Some(path), .. } if path == &probe),
            "the call site knows the path, so it must be in the error, got {err:?}"
        );
    }

    #[test]
    fn source_chain_flattens_nested_causes() {
        let err = Error::io(io::Error::from(io::ErrorKind::NotFound));
        let rendered = source_chain(&err);
        assert!(
            !rendered.contains("(none)"),
            "the io error must show up in the chain, got {rendered:?}"
        );
        assert_eq!(source_chain(&Error::Internal("boom".into())), "(none)");
    }

    #[test]
    fn demo_walks_every_variant() {
        let probe = missing_path();
        assert!(
            !probe.exists(),
            "the demo needs a path that cannot be opened, but {probe:?} exists"
        );

        let sink = Demo::new("error_enum");
        demo(&sink).expect("the demo reports its own failures");
        let text = sink.render();

        let with_path = format!("io error on {}: ", probe.display());
        for expected in [
            "key is 300 bytes, the limit is 255 bytes",
            "key \"user:42\" was not found",
            "corrupt record in file 3 at offset 4096: crc32 mismatch",
            "io error: ",
            with_path.as_str(),
            "internal error: file id space exhausted",
        ] {
            assert!(
                text.contains(expected),
                "demo output is missing {expected:?}"
            );
        }
        assert!(
            text.contains("source  : "),
            "demo must show the source chain"
        );
    }
}
