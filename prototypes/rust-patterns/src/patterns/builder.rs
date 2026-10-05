//! Hand-written builder: named, chained construction.
//!
//! The pattern: when a type has several fields and most of them are optional, do
//! not make its constructor positional. Add a second type — the builder — whose
//! methods name one value each, take `self` and return `Self`, so the call site
//! becomes a chain that reads top to bottom and mentions only what differs from
//! the defaults.
//!
//! Run `cargo run builder` to see the positional call it replaces and the chain
//! that replaces it. The reasoning lives on [`CommandBuilder`]; `#[cfg(test)]
//! mod tests` at the bottom of this file pins the defaults, the append order and
//! the rendered walkthrough, and a `compile_fail` example on
//! [`CommandBuilder::build`] pins the one thing a test cannot: a consumed builder
//! cannot be built twice.
//!
//! ```
//! use rust_patterns::patterns::builder::CommandBuilder;
//!
//! let command = CommandBuilder::new()
//!     .program("cargo")
//!     .arg("test")
//!     .timeout_secs(600)
//!     .build();
//!
//! assert_eq!(command.program(), "cargo");
//! assert_eq!(command.args(), &["test"]);
//! assert_eq!(command.timeout_secs(), 600);
//! ```

use crate::demo::{Demo, DemoResult};

/// Timeout a [`Command`] gets when the caller does not pick one.
const DEFAULT_TIMEOUT_SECS: u64 = 30;

/// A command that is ready to hand to a runner.
///
/// Every field is private and only reachable through the getters below. That is
/// the second half of the pattern: the builder writes the fields, everybody else
/// reads them, so a `Command` that exists is a `Command` that was built — there
/// is no literal to keep in sync when a field is added.
#[derive(Debug, PartialEq, Eq)]
pub struct Command {
    program: String,
    args: Vec<String>,
    timeout_secs: u64,
}

impl Command {
    /// The program to run.
    #[must_use]
    pub fn program(&self) -> &str {
        &self.program
    }

    /// The arguments, in the order they were added.
    #[must_use]
    pub fn args(&self) -> &[String] {
        &self.args
    }

    /// How long the command may run before the runner kills it.
    #[must_use]
    pub fn timeout_secs(&self) -> u64 {
        self.timeout_secs
    }
}

/// Builds a [`Command`] one named value at a time.
///
/// # Why a second type
///
/// | Approach | What it buys | What it costs |
/// | --- | --- | --- |
/// | Positional `Command::new(program, args, timeout)` | One line, no extra type | Call sites are unreadable (which number is the timeout?), and every new field breaks every call site |
/// | Builder (this file) | The values are named at the call site, defaults only have to be overridden when they are wrong, repeatable fields append | A second type, and a setter per field to keep in sync with it |
/// | Public fields + `..Default::default()` | No code at all | Only for public fields; `String` / `Vec` boilerplate and no place to validate or append |
///
/// Rule of thumb: **reach for a builder once the call site no longer explains
/// itself** — several optional fields, repeated fields, or a `Vec` the caller
/// would otherwise assemble by hand.
///
/// # Why the setters take `self`
///
/// `&mut self` works too, and lets the same builder be filled in and reused.
/// Taking `self` moves the builder through the chain and lets
/// [`build`](Self::build) consume it, so the compiler — not a comment — says a
/// half-configured builder cannot be used twice, and the whole construction
/// stays a single expression, with no `mut` binding in sight.
///
/// # When `build` returns a `Result`
///
/// Nothing here is mandatory, so `build` cannot fail. The first field that would
/// change that is the timeout — `timeout_secs(0)` has no defined meaning — so a
/// runner that refuses it turns `build` into `build(self) -> Result<Command, Error>`
/// (the error enum from the `error_enum` pattern). The other shape puts the
/// requirement in the type instead: *typestate*, where `program(..)` returns a
/// different builder type and only the type that has everything set owns a
/// `build` method, so a required field cannot be skipped. Typestate is a pattern
/// of its own; this file stays with the plain form.
///
/// A derive macro (`derive_builder`) generates setters like the ones below from
/// field attributes. Its *default* pattern borrows instead of consuming: the
/// generated setters take `&mut self`, return `&mut Self`, and the generated
/// `build` takes `&self`, which is what lets the same builder be built more than
/// once. (`#[builder(pattern = "owned")]` opts into consuming setters instead.)
/// Writing the setters by hand first is what makes that generated code readable.
#[derive(Debug)]
pub struct CommandBuilder {
    program: String,
    args: Vec<String>,
    timeout_secs: u64,
}

impl CommandBuilder {
    /// Start from the defaults: no program, no arguments, and the 30-second
    /// timeout in `DEFAULT_TIMEOUT_SECS`.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Which program to run, replacing whatever was set before.
    #[must_use]
    pub fn program(mut self, value: impl Into<String>) -> Self {
        self.program = value.into();
        self
    }

    /// Append one argument — call it once per argument.
    #[must_use]
    pub fn arg(mut self, value: impl Into<String>) -> Self {
        self.args.push(value.into());
        self
    }

    /// Override the default timeout.
    #[must_use]
    pub fn timeout_secs(mut self, value: u64) -> Self {
        self.timeout_secs = value;
        self
    }

    /// Finish the command and consume the builder.
    ///
    /// Consuming `self` is the heart of the pattern: the builder is gone
    /// afterwards, so it cannot be filled in any further and cannot be built
    /// twice. The compiler enforces that, not this comment — which is what the
    /// `compile_fail` example below pins:
    ///
    /// ```compile_fail
    /// use rust_patterns::patterns::builder::CommandBuilder;
    ///
    /// let builder = CommandBuilder::new().program("cargo");
    /// let _first = builder.build();
    /// // `builder` was moved into the line above, so this cannot compile.
    /// let _second = builder.build();
    /// ```
    #[must_use]
    pub fn build(self) -> Command {
        Command {
            program: self.program,
            args: self.args,
            timeout_secs: self.timeout_secs,
        }
    }
}

impl Default for CommandBuilder {
    /// The single source of the defaults; [`CommandBuilder::new`] delegates here,
    /// so `default()` and `new()` cannot drift apart.
    fn default() -> Self {
        Self {
            program: String::new(),
            args: Vec::new(),
            timeout_secs: DEFAULT_TIMEOUT_SECS,
        }
    }
}

/// The program and its arguments on one line, ready for the walkthrough.
fn one_line(command: &Command) -> String {
    let mut line = command.program().to_owned();
    for arg in command.args() {
        line.push(' ');
        line.push_str(arg);
    }
    line
}

/// Print the walkthrough into `sink`.
///
/// The demo never prints itself: it writes numbered steps into the shared
/// [`Demo`] sink, so the tests can assert on exactly the text the CLI prints.
pub fn demo(sink: &Demo) -> DemoResult {
    sink.step("Positional construction leaves the reader guessing what each value means");
    sink.detail(r#"hypothetically: Command::new("cargo", vec!["test".to_string()], 30)"#);

    sink.step("The builder names every value, and only what differs from the defaults");
    let command = CommandBuilder::new()
        .program("cargo")
        .arg("test")
        .arg("--quiet")
        .build();
    sink.detail(one_line(&command));
    sink.detail(format!(
        "timeout: {}s (the default)",
        command.timeout_secs()
    ));

    sink.step("Repeatable fields append in call order, so the caller builds no `Vec`");
    let long_running = CommandBuilder::new()
        .program("cargo")
        .arg("test")
        .timeout_secs(600)
        .build();
    sink.detail(one_line(&long_running));
    sink.detail(format!(
        "timeout: {}s (overridden)",
        long_running.timeout_secs()
    ));

    sink.step("Each setter took `self`, so `build` consumed the builder it was called on");
    sink.detail("a half-configured builder cannot leak into a second command by mistake");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_fresh_builder_uses_the_defaults() {
        let command = CommandBuilder::new().build();
        assert_eq!(command.program(), "");
        assert!(command.args().is_empty(), "{:?}", command.args());
        assert_eq!(command.timeout_secs(), DEFAULT_TIMEOUT_SECS);
        assert_eq!(
            CommandBuilder::default().build(),
            command,
            "`default()` and `new()` must not drift apart"
        );
    }

    #[test]
    fn setters_name_each_value_and_append_in_call_order() {
        let command = CommandBuilder::new()
            .program("cargo")
            .arg("test")
            .arg("--quiet")
            .timeout_secs(600)
            .build();
        assert_eq!(command.program(), "cargo");
        assert_eq!(command.args(), &["test", "--quiet"]);
        assert_eq!(command.timeout_secs(), 600);
    }

    #[test]
    fn a_setter_replaces_a_value_the_builder_already_has() {
        let command = CommandBuilder::new()
            .program("cargo")
            .program("just")
            .timeout_secs(1)
            .timeout_secs(2)
            .build();
        assert_eq!(command.program(), "just");
        assert_eq!(command.timeout_secs(), 2);
    }

    #[test]
    fn one_line_has_no_trailing_space_without_arguments() {
        let command = CommandBuilder::new().program("cargo").build();
        assert_eq!(one_line(&command), "cargo");
    }

    #[test]
    fn demo_walks_the_pattern() {
        let sink = Demo::new("builder");
        demo(&sink).expect("the demo reports its own failures");
        let text = sink.render();

        for expected in [
            "cargo test --quiet",
            "timeout: 30s (the default)",
            "Repeatable fields append in call order",
            "timeout: 600s (overridden)",
            "setter took `self`",
        ] {
            assert!(
                text.contains(expected),
                "demo output is missing {expected:?}"
            );
        }
        assert!(
            text.contains("1. Positional construction leaves the reader guessing"),
            "the walkthrough must start at the positional call it replaces"
        );
    }
}
