//! The prototype's only entry point.
//!
//! ```text
//! cargo run               -> list the patterns
//! cargo run error_enum    -> run one pattern's demo
//! ```
//!
//! Exit codes: `0` fine, `1` a demo failed, `2` the argument did not match any
//! pattern (or there was more than one argument).

use std::fmt::Write as _;
use std::process::ExitCode;

use rust_patterns::demo;
use rust_patterns::patterns::{self, PATTERNS};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();

    match args.as_slice() {
        [] => {
            print!("{}", listing());
            ExitCode::SUCCESS
        }
        [id] => run(id),
        _ => {
            eprintln!("usage: cargo run [<pattern-id>]");
            eprintln!("got {} arguments, expected at most one", args.len());
            ExitCode::from(2)
        }
    }
}

/// The text printed with no argument: every pattern, and how to run one.
fn listing() -> String {
    let mut text = String::from("rust-patterns\n\n");
    let width = PATTERNS.iter().map(|p| p.id.len()).max().unwrap_or(0);
    for pattern in PATTERNS {
        let _ = writeln!(text, "  {:width$}  {}", pattern.id, pattern.summary);
    }
    text.push_str("\nrun one with: cargo run <id>\n");
    text
}

/// Run the pattern whose id is `id`, or report the available ones.
fn run(id: &str) -> ExitCode {
    if let Some(pattern) = patterns::find(id) {
        demo::run(pattern.id, pattern.demo)
    } else {
        eprintln!("no pattern called {id:?}");
        eprintln!(
            "available: {}",
            PATTERNS
                .iter()
                .map(|pattern| pattern.id)
                .collect::<Vec<_>>()
                .join(", ")
        );
        ExitCode::from(2)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn listing_shows_every_pattern_and_the_hint() {
        let text = listing();
        for pattern in PATTERNS {
            assert!(
                text.contains(pattern.id),
                "listing is missing {}",
                pattern.id
            );
        }
        assert!(text.contains("run one with: cargo run <id>"), "{text}");
    }

    #[test]
    fn an_unknown_id_is_an_error() {
        assert_eq!(run("definitely-not-a-pattern"), ExitCode::from(2));
    }
}
