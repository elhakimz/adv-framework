// PROPERTY TEST — lives at tests/property_tests.rs, which Cargo compiles
// as its own integration-test binary target. `cargo nextest run --test
// property_tests` runs ONLY this file — no tag, marker, or config
// needed, the filename+location IS the target selector.
//
// proptest generates inputs and shrinks any failure to the smallest
// reproducing case, same role as Hypothesis/jqwik/FsCheck/rapid/fast-check
// in the other language pipelines in this skill.

use proptest::prelude::*;

// use my_crate::calculate_something;

proptest! {
    #[test]
    fn is_commutative(a: i64, b: i64) {
        // prop_assert_eq!(calculate_something(a, b), calculate_something(b, a));
    }

    #[test]
    fn output_is_never_negative(values in prop::collection::vec(any::<i32>(), 1..20)) {
        // let result = calculate_something(&values);
        // prop_assert!(result >= 0);
    }
}
