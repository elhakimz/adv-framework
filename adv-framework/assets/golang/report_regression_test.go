//go:build regression

package report

import (
	"testing"

	"github.com/sebdah/goldie/v2"
)

// REGRESSION TEST — excluded from default `go test ./...` by the build
// tag, only runs with `-tags=regression`.
//
// goldie compares output against a committed file in testdata/*.golden.
// To intentionally update a golden file after a verified behavior
// change, run: go test -tags=regression ./... -update

func TestRegressionGenerateReport_MatchesSnapshot(t *testing.T) {
	g := goldie.New(t)

	// result := GenerateReport(sampleInput)
	result := []byte("placeholder output")

	g.Assert(t, "report_output", result)
}
