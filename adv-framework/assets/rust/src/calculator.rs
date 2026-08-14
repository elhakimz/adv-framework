// UNIT TEST — inline #[cfg(test)] module, idiomatic Rust placement.
// Part of the `--lib` target, so `cargo nextest run --lib` in the
// `unit-test` CI job picks this up automatically. tests/property_tests.rs
// and tests/regression_tests.rs are separate Cargo targets entirely —
// this file's tests can never accidentally run alongside them or vice versa.

pub fn calculate_something(a: i64, b: i64) -> i64 {
    a + b // placeholder
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_case_returns_expected() {
        assert_eq!(calculate_something(10, 5), 15);
    }
}
