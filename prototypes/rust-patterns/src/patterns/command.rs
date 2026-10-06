//! Hand-written command: a request as a value you can queue and take back.
//!
//! The pattern: wrap an action in a value of its own, so the code that *decides*
//! what to do is not the code that does it. That is all it takes to get the
//! things the pattern is used for — a `Vec` of commands is a queue (run later, in
//! another order, or not at all), and a command that says how to cancel itself is
//! an undo stack.
//!
//! Run `cargo run command` for the walkthrough: a queue built without touching
//! the document, the queue running, then undo, command by command. The reasoning
//! lives on [`Edit`] and [`Editor`]; `#[cfg(test)] mod tests` at the bottom of
//! this file pins the queue order, the undo round trip and the printed
//! walkthrough.
//!
//! ```
//! use rust_patterns::patterns::command::{Edit, Editor};
//!
//! let mut editor = Editor::new("hello");
//! editor.run(Edit::insert(0, "say "));
//! assert_eq!(editor.text(), "say hello");
//!
//! assert!(editor.undo());
//! assert_eq!(editor.text(), "hello");
//! ```

use std::fmt;

use crate::demo::{Demo, DemoResult};

/// The document a command runs against: characters, so a position is a character
/// and `1` means the same thing to whoever counted the letters and to the code.
///
/// A type alias rather than a newtype: it names the representation without
/// wrapping it. The cost is that any `Vec<char>` is accepted as a document and
/// there is nowhere to hold an invariant about one — wrapping it
/// (`struct Document(Vec<char>)`) is the move for when that matters.
pub type Document = Vec<char>;

/// One command: *what* to change, not the change itself.
///
/// A set of commands known at compile time is an `enum` in Rust, and then `match`
/// stays exhaustive: adding a kind of command breaks every place that runs one
/// until the new case is handled, and a single `Vec` holds them all with nothing
/// allocated and nothing declared per command. (When the set is open instead —
/// commands the program only meets at run time — the same shape moves behind a
/// box: `Box<dyn FnOnce(&mut Document) -> Edit>`. That costs one allocation per
/// command and gives up the matching, and is a pattern of its own.)
///
/// # Why `apply` consumes the command and returns the undo
///
/// Undoing "delete 6 characters at 0" needs those 6 characters, and the `Edit`
/// value that was built never saw them. So a command cannot know its own undo
/// until it runs: `apply` *returns* the command that cancels it, minted from what
/// it just found. `Delete` hands the removed text to the `Insert` that puts it
/// back; `Insert` counts what it wrote and hands `Delete` a span.
///
/// Consuming `self` is what lets that happen without cloning, and it says what the
/// pattern means: a command that has run is a different value, and running one
/// twice is a different request.
///
/// # Why it is printable
///
/// `Display` below is not decoration. A closed set of commands is data, so a
/// queue of them can be logged — before it runs, in order — which is one of the
/// reasons to reach for this pattern at all.
#[derive(Debug, PartialEq, Eq)]
pub enum Edit {
    /// Type `text` in at character position `at`.
    Insert {
        /// Where the insertion starts.
        at: usize,
        /// The text to insert.
        text: String,
    },

    /// Remove `len` characters starting at `at`.
    Delete {
        /// Where the removal starts.
        at: usize,
        /// How many characters to remove.
        len: usize,
    },
}

impl Edit {
    /// Build the command that types `text` in at `at`.
    ///
    /// A constructor instead of the variant literal, so the call site reads like
    /// the action (`Edit::insert(0, "say ")`) and a new field would not touch it.
    #[must_use]
    pub fn insert(at: usize, text: impl Into<String>) -> Self {
        Self::Insert {
            at,
            text: text.into(),
        }
    }

    /// Build the command that removes `len` characters starting at `at`.
    #[must_use]
    pub fn delete(at: usize, len: usize) -> Self {
        Self::Delete { at, len }
    }

    /// Whether running this command would leave the document unchanged.
    ///
    /// The inverse of a command that changed nothing is itself a no-op, which is
    /// how `Editor::run` recognizes one: there is nothing to take back, so it is
    /// not put on the undo stack.
    fn is_noop(&self) -> bool {
        match self {
            Self::Insert { text, .. } => text.is_empty(),
            Self::Delete { len, .. } => *len == 0,
        }
    }

    /// Run this command against `doc`, returning the command that takes it back.
    ///
    /// The command holds no reference to a document, which is what lets a queue
    /// of them be built, stored or moved before it is aimed at one. A command
    /// with a degenerate span — an empty text, a zero length — changes nothing and
    /// returns an inverse that is degenerate the same way, which is how
    /// [`Editor::run`] notices that there is nothing to take back.
    ///
    /// # Panics
    ///
    /// When the span does not fit `doc` — `at` past the end, or `at + len` past
    /// it — exactly as `Vec::splice` panics. The walkthrough never does that; a
    /// real editor would return a `Result` instead (see the `error_enum` pattern).
    ///
    /// Taking `self` means a command runs once, and the compiler enforces it:
    ///
    /// ```compile_fail,E0382
    /// use rust_patterns::patterns::command::{Document, Edit};
    ///
    /// let mut doc: Document = "hello".chars().collect();
    /// let command = Edit::insert(0, "say ");
    /// command.apply(&mut doc);
    /// // `command` moved into the line above, so this cannot compile: the undo
    /// // of that change is the value `apply` returned, not this one.
    /// command.apply(&mut doc);
    /// ```
    #[must_use = "the returned command is the undo of this one"]
    pub fn apply(self, doc: &mut Document) -> Edit {
        match self {
            Self::Insert { at, text } => {
                let len = text.chars().count();
                doc.splice(at..at, text.chars());
                Self::delete(at, len)
            }
            Self::Delete { at, len } => {
                let end = at.saturating_add(len);
                let removed: String = doc.splice(at..end, []).collect();
                Self::insert(at, removed)
            }
        }
    }
}

// `Display`, not just the derived `Debug`: it is the wording this file's
// walkthrough and tests stand on, so it is owned here instead of coming out of
// the enum's shape.
impl fmt::Display for Edit {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            // `{text:?}` on purpose: the quoting and escaping of `str` are what
            // keep an insert that spans lines on one logged line.
            Self::Insert { at, text } => write!(f, "insert {text:?} at {at}"),
            Self::Delete { at, len } => write!(f, "delete {len} character(s) at {at}"),
        }
    }
}

/// The document, plus the commands that ran — the queue and the undo stack.
///
/// The document is private and only [`run`](Self::run) changes it, so the undo
/// stack cannot go stale: every command in it was minted by a change that really
/// happened. Undoing pops one and applies it, which by construction hands back the
/// command that redoes it — redo is that value, pushed onto a second stack.
#[derive(Debug)]
pub struct Editor {
    /// The document, as characters so a position is a character.
    doc: Document,
    /// The undo of each command that ran, newest last: the undo stack.
    undo: Vec<Edit>,
}

impl Editor {
    /// An editor over `text`, with nothing to undo.
    #[must_use]
    pub fn new(text: impl AsRef<str>) -> Self {
        Self {
            doc: text.as_ref().chars().collect(),
            undo: Vec::new(),
        }
    }

    /// The document as it stands.
    ///
    /// Allocating, because the document is kept as characters: a `String`-backed
    /// one could hand out `&str`, at the price of positions being byte offsets.
    #[must_use]
    pub fn text(&self) -> String {
        self.doc.iter().collect()
    }

    /// Run one command, remembering how to take it back.
    ///
    /// A command that changes nothing — an empty insert, a zero-length delete — is
    /// still checked against the document, but not remembered: there is nothing to
    /// take back.
    ///
    /// # Panics
    ///
    /// When the command's span does not fit the document (see [`Edit::apply`]).
    /// Nothing has changed at that point, so the document and the undo stack are
    /// both left as they were.
    pub fn run(&mut self, command: Edit) {
        let inverse = command.apply(&mut self.doc);
        if !inverse.is_noop() {
            self.undo.push(inverse);
        }
    }

    /// Run a queue of commands in order.
    ///
    /// Not a transaction: if a command panics, the commands before it stay applied
    /// and stay undoable.
    pub fn run_all(&mut self, commands: impl IntoIterator<Item = Edit>) {
        for command in commands {
            self.run(command);
        }
    }

    /// Take back the last command; `false` when there is nothing to take back.
    pub fn undo(&mut self) -> bool {
        let Some(inverse) = self.undo.pop() else {
            return false;
        };
        // Applying an inverse hands back the command that redoes it. A redo stack
        // would keep that value; this editor deliberately stops at undo.
        let _ = inverse.apply(&mut self.doc);
        true
    }
}

/// Print the walkthrough into `sink`.
///
/// The demo never prints itself: it writes numbered steps into the shared
/// [`Demo`] sink, so the tests can assert on exactly the text the CLI prints.
pub fn demo(sink: &Demo) -> DemoResult {
    sink.step("A command is a value: building one changes nothing yet");
    let document = "hello world";
    // On `document`: append at the end, then drop the leading "hello ".
    let queue = vec![
        Edit::insert(document.chars().count(), "!"),
        Edit::delete(0, 6),
    ];
    sink.detail(format!(
        "queue: {}",
        queue
            .iter()
            .map(Edit::to_string)
            .collect::<Vec<_>>()
            .join(" | ")
    ));
    sink.detail("`String::insert_str` would do this here and now, leaving nothing behind");

    sink.step("The document is untouched until a command runs");
    let mut editor = Editor::new(document);
    sink.detail(format!("still {:?}", editor.text()));

    sink.step("Run the queue: a `Vec` of commands is the whole queue");
    editor.run_all(queue);
    sink.detail(format!("-> {:?}", editor.text()));

    sink.step("Undo: every command handed back the command that cancels it");
    while editor.undo() {
        sink.detail(format!("undo -> {:?}", editor.text()));
    }

    sink.step("That is the pattern: decide now, run later, take back by running the inverse");
    sink.detail("redo is one more stack of those inverses; an open set of commands needs a box");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_command_edits_where_it_says() {
        let mut editor = Editor::new("hello world");
        editor.run(Edit::insert(11, "!"));
        assert_eq!(editor.text(), "hello world!");
        editor.run(Edit::delete(0, 6));
        assert_eq!(editor.text(), "world!");
    }

    #[test]
    fn a_position_is_a_character_not_a_byte() {
        let mut editor = Editor::new("héllo");
        editor.run(Edit::delete(1, 1));
        assert_eq!(editor.text(), "hllo");
    }

    #[test]
    fn a_span_may_end_at_the_last_character() {
        let mut editor = Editor::new("hello world");
        editor.run(Edit::delete(6, 5));
        assert_eq!(editor.text(), "hello ");

        // `at == doc.len()` is the other end of the same boundary.
        editor.run(Edit::insert(6, "world"));
        assert_eq!(editor.text(), "hello world");
    }

    #[test]
    #[should_panic]
    fn a_span_past_the_end_panics() {
        // Deliberately no `expected`: the message is `Vec::splice`'s wording, not
        // this file's, so pinning it would tie the test to std's phrasing.
        let mut editor = Editor::new("hello");
        editor.run(Edit::delete(100, 1));
    }

    #[test]
    fn apply_returns_the_command_that_undoes_it() {
        let mut doc: Document = "hello".chars().collect();

        let undo = Edit::insert(1, "ey").apply(&mut doc);
        assert_eq!(undo, Edit::delete(1, 2));
        assert_eq!(doc.iter().collect::<String>(), "heyello");

        // The removed text travelled into the inverse, so it restores exactly.
        let redo = undo.apply(&mut doc);
        assert_eq!(redo, Edit::insert(1, "ey"));
        assert_eq!(doc.iter().collect::<String>(), "hello");
    }

    #[test]
    fn undo_walks_back_through_the_queue() {
        let mut editor = Editor::new("hello world");
        editor.run_all([Edit::insert(11, "!"), Edit::delete(0, 6)]);
        assert_eq!(editor.text(), "world!");

        assert!(editor.undo());
        assert_eq!(editor.text(), "hello world!");
        assert!(editor.undo());
        assert_eq!(editor.text(), "hello world");
        assert!(!editor.undo(), "the undo stack is empty");
    }

    #[test]
    fn a_command_that_changes_nothing_is_not_remembered() {
        let mut editor = Editor::new("hello");
        editor.run(Edit::insert(3, ""));
        editor.run(Edit::delete(3, 0));
        assert_eq!(editor.text(), "hello");
        assert!(
            !editor.undo(),
            "nothing changed, so nothing can be taken back"
        );
    }

    #[test]
    fn a_command_can_be_logged() {
        assert_eq!(Edit::insert(0, "say ").to_string(), r#"insert "say " at 0"#);
        assert_eq!(Edit::delete(4, 2).to_string(), "delete 2 character(s) at 4");
    }

    #[test]
    fn demo_walks_the_pattern() {
        let sink = Demo::new("command");
        demo(&sink).expect("the demo reports its own failures");
        let text = sink.render();

        for expected in [
            r#"queue: insert "!" at 11 | delete 6 character(s) at 0"#,
            "still \"hello world\"",
            "-> \"world!\"",
            "undo -> \"hello world!\"",
            "undo -> \"hello world\"",
            "That is the pattern",
        ] {
            assert!(
                text.contains(expected),
                "demo output is missing {expected:?}"
            );
        }
        assert!(
            text.contains("1. A command is a value"),
            "the walkthrough must start by building a command, not by running one"
        );
    }
}
