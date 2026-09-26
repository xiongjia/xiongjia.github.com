//! The pattern modules and the table the binary dispatches on.
//!
//! A pattern is registered with a `pub mod <id>;` line and a row in
//! [`PATTERNS`], next to its own file under this directory.

use crate::demo::DemoFn;

pub mod error_enum;

/// One runnable pattern.
///
/// Deliberately tiny: the CLI id, a one-line summary for the listing, and the
/// demo function. Book references, longer explanations and status live in the
/// prototype README and in the pattern's doc comments.
pub struct Pattern {
    /// What to type: `cargo run <id>` (matches the module and file name).
    pub id: &'static str,
    /// One line shown by the listing, and by `just` with no argument.
    pub summary: &'static str,
    /// The walkthrough printed when this pattern runs.
    pub demo: DemoFn,
}

/// Every pattern, in the order the listing shows them.
pub const PATTERNS: &[Pattern] = &[Pattern {
    id: "error_enum",
    summary: "hand-written error enum: variants, context helpers, Display/source chain",
    demo: error_enum::demo,
}];

/// Look a pattern up by the id typed on the command line.
#[must_use]
pub fn find(id: &str) -> Option<&'static Pattern> {
    PATTERNS.iter().find(|pattern| pattern.id == id)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ids_are_unique_and_described() {
        assert!(!PATTERNS.is_empty(), "the listing would be empty");
        for pattern in PATTERNS {
            assert!(!pattern.id.is_empty(), "a pattern id is empty");
            assert!(
                !pattern.summary.is_empty(),
                "{} has no summary for the listing",
                pattern.id
            );
            assert!(
                !pattern.id.contains(' '),
                "{} must be typable without quoting",
                pattern.id
            );
        }

        let mut ids: Vec<&str> = PATTERNS.iter().map(|pattern| pattern.id).collect();
        let total = ids.len();
        ids.sort_unstable();
        ids.dedup();
        assert_eq!(ids.len(), total, "duplicate ids: {ids:?}");
    }

    #[test]
    fn every_registered_pattern_is_findable_by_id() {
        for pattern in PATTERNS {
            let found = find(pattern.id).expect("a registered id must be findable");
            assert_eq!(found.id, pattern.id);
        }
        assert!(find("definitely-not-a-pattern").is_none());
    }
}
