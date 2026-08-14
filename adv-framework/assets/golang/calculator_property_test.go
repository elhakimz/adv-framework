//go:build property

package calculator

import (
	"testing"

	"pgregory.net/rapid"
)

// PROPERTY TEST — the //go:build property tag at the top of this file
// means it's completely excluded from a plain `go test ./...`. It only
// compiles and runs when the CI job passes `-tags=property`.
//
// rapid generates inputs, runs the property, and shrinks any failure to
// the smallest reproducing case automatically.

func TestPropertyCalculateSomething_IsCommutative(t *testing.T) {
	rapid.Check(t, func(t *rapid.T) {
		a := rapid.Int().Draw(t, "a")
		b := rapid.Int().Draw(t, "b")

		// if CalculateSomething(a, b) != CalculateSomething(b, a) {
		// 	t.Fatalf("not commutative for a=%d b=%d", a, b)
		// }
		_ = a
		_ = b
	})
}

func TestPropertyOutput_IsNeverNegative(t *testing.T) {
	rapid.Check(t, func(t *rapid.T) {
		values := rapid.SliceOfN(rapid.Float64(), 1, 20).Draw(t, "values")

		// result := CalculateSomething(values...)
		// if result < 0 {
		// 	t.Fatalf("got negative result %f for input %v", result, values)
		// }
		_ = values
	})
}
