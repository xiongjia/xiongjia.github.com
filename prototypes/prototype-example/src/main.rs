// Minimal Rust prototype: greets the caller, validates that a non-Python
// toolchain project sits cleanly in prototypes/ without disturbing the
// MkDocs / ruff / mdformat workflow.

fn main() {
    let name = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "prototype".to_string());
    println!("hello from prototype-example, {name}!");
}
