//! Shared demo plumbing: the [`Demo`] sink and the [`run`] helper.
//!
//! Patterns never call `println!` themselves. They write into a [`Demo`], which
//! makes the same `demo` function usable in two places:
//!
//! - the binary prints [`Demo::render`]'s output for a human
//! - the module's own tests assert on the very same text (see
//!   `patterns::error_enum`'s tests), so a walkthrough cannot silently rot

use std::cell::{Cell, RefCell};
use std::fmt::Write as _;
use std::process::ExitCode;

/// Result type of every pattern demo.
///
/// Patterns have their own error types (that *is* one of the patterns worth
/// learning), so the table in [`crate::patterns`] needs one signature for all
/// of them: anything implementing [`std::error::Error`] can bubble up here.
pub type DemoResult = Result<(), Box<dyn std::error::Error>>;

/// Signature of a pattern demo: writes its walkthrough into the sink.
///
/// A shared `&Demo` (not `&mut Demo`) because the sink uses interior mutability
/// — see [`Demo`].
pub type DemoFn = fn(&Demo) -> DemoResult;

/// Numbered walkthrough sink.
///
/// Writes go through a **shared** `&Demo`: the body and step counter live in
/// [`RefCell`] and [`Cell`], so a demo takes `&Demo` and no caller ever needs a
/// `mut` binding. The trade-off is real and deliberate: the compiler can no
/// longer prove the mutation, so overlapping borrows become a runtime panic
/// instead of a compile error — which is why every method below borrows, writes
/// and releases before returning.
///
/// Threading follows from that choice: `Cell` and `RefCell` make `Demo` not
/// [`Sync`], which is fine for a single-threaded CLI run; a sink that had to be
/// shared across threads would hold a `Mutex` instead.
///
/// ```
/// use rust_patterns::demo::Demo;
///
/// let sink = Demo::new("example");   // no `mut` needed
/// sink.step("the first thing that happens");
/// sink.detail("a value worth showing");
/// let text = sink.render();
///
/// assert!(text.contains("1. the first thing that happens"));
/// assert!(text.contains("a value worth showing"));
/// ```
#[derive(Debug)]
pub struct Demo {
    title: String,
    /// Behind a `RefCell` so `step`/`detail` can take `&self`.
    body: RefCell<String>,
    /// A `Cell` for the same reason (`usize` is `Copy`, no `RefCell` needed).
    steps: Cell<usize>,
}

impl Demo {
    /// Start a walkthrough called `title` (usually the pattern id).
    #[must_use]
    pub fn new(title: impl Into<String>) -> Self {
        Self {
            title: title.into(),
            body: RefCell::new(String::new()),
            steps: Cell::new(0),
        }
    }

    /// Add the next numbered step.
    ///
    /// The `write!` result is ignored on purpose: writing into a `String` cannot
    /// fail. The one way this can panic is a `RefCell` borrow conflict, which the
    /// borrow-write-release discipline in this file avoids.
    pub fn step(&self, text: impl AsRef<str>) {
        let step = self.steps.get() + 1;
        self.steps.set(step);
        let _ = writeln!(self.body.borrow_mut(), "{step:>2}. {}", text.as_ref());
    }

    /// Add an indented detail line to the current step.
    pub fn detail(&self, text: impl AsRef<str>) {
        let _ = writeln!(self.body.borrow_mut(), "    {}", text.as_ref());
    }

    /// The rendered walkthrough: header, numbered steps, closing summary.
    #[must_use]
    pub fn render(&self) -> String {
        format!(
            "▶ {}\n{}\n✓ {} step(s) done\n",
            self.title,
            self.body.borrow().trim_end(),
            self.steps.get()
        )
    }
}

/// Run a demo, print it, and map the outcome to an exit code.
///
/// Used by the binary; patterns are expected to print *something* even when
/// they fail, which is exactly what happens here: the steps collected so far
/// are printed before the error is reported.
pub fn run(title: &str, demo_fn: DemoFn) -> ExitCode {
    let sink = Demo::new(title);
    match demo_fn(&sink) {
        // `render` already ends with a newline, so print it as-is.
        Ok(()) => {
            print!("{}", sink.render());
            ExitCode::SUCCESS
        }
        Err(err) => {
            print!("{}", sink.render());
            eprintln!("✗ {title} stopped: {err}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn steps_are_numbered_from_one() {
        let sink = Demo::new("demo");
        sink.step("first thing");
        sink.step("second thing");
        let text = sink.render();
        assert!(text.contains("1. first thing"), "{text}");
        assert!(text.contains("2. second thing"), "{text}");
    }

    #[test]
    fn details_are_indented_under_the_step() {
        let sink = Demo::new("demo");
        sink.step("a step");
        sink.detail("a value");
        assert!(sink.render().contains("\n    a value\n"));
    }

    #[test]
    fn render_frames_the_walkthrough() {
        let sink = Demo::new("error_enum");
        sink.step("one");
        sink.step("two");
        let text = sink.render();
        assert!(text.starts_with("▶ error_enum\n"), "{text}");
        assert!(text.ends_with("✓ 2 step(s) done\n"), "{text}");
    }

    #[test]
    fn an_empty_demo_still_renders() {
        let text = Demo::new("nothing").render();
        assert!(text.contains("▶ nothing"), "{text}");
        assert!(text.contains("0 step(s) done"), "{text}");
    }

    #[test]
    fn a_failing_demo_reports_failure() {
        // The annotation is what turns the closure into a `DemoFn`; the test
        // only cares about the exit code it maps to.
        let boom: DemoFn = |_| Err("no way".into());
        assert_eq!(run("boom", boom), ExitCode::FAILURE);
    }

    #[test]
    fn a_successful_demo_reports_success() {
        let fine: DemoFn = |sink| {
            sink.step("all good");
            Ok(())
        };
        assert_eq!(run("fine", fine), ExitCode::SUCCESS);
    }
}
