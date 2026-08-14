// Example showing how the three test categories are distinguished so the
// CI pipeline's --filter "Category=..." selections actually work.
// Adapt namespaces to your real project structure.
//
// NuGet packages needed in the test project (.csproj):
//   xunit
//   xunit.runner.visualstudio
//   coverlet.collector
//   FsCheck.Xunit          <- property-based testing
//   Verify.Xunit           <- snapshot/golden-file regression testing
//   SecurityCodeScan.VS2019 (referenced in the main project, not test project)

using FsCheck;
using FsCheck.Xunit;
using VerifyXunit;
using Xunit;

namespace MyProject.Tests;

// ---------------------------------------------------------------------------
// UNIT TEST — no [Trait], picked up by the default `unit-test` CI job
// ---------------------------------------------------------------------------

public class CalculatorTests
{
    [Fact]
    public void CalculateSomething_KnownCase_ReturnsExpected()
    {
        // var result = Calculator.CalculateSomething(10, 5);
        // Assert.Equal(15, result);
    }
}

// ---------------------------------------------------------------------------
// PROPERTY TEST — [Trait("Category","Property")], only runs in the
// `property-test` CI job. FsCheck generates hundreds of inputs and
// shrinks any failure to the smallest reproducing case.
// ---------------------------------------------------------------------------

[Trait("Category", "Property")]
public class CalculatorPropertyTests
{
    [Property]
    public bool CalculateSomething_IsCommutative(int a, int b)
    {
        // return Calculator.CalculateSomething(a, b)
        //     == Calculator.CalculateSomething(b, a);
        return true;
    }

    [Property]
    public Property Output_IsNeverNegative(NonEmptyArray<double> values)
    {
        // var result = Calculator.CalculateSomething(values.Get);
        // return (result >= 0).ToProperty();
        return true.ToProperty();
    }
}

// ---------------------------------------------------------------------------
// REGRESSION TEST — [Trait("Category","Regression")], only runs in the
// `golden-file-regression` CI job. Verify compares serialized output
// against a committed *.verified.txt file; first run creates a
// *.received.txt for you to review and rename/accept.
// ---------------------------------------------------------------------------

[Trait("Category", "Regression")]
[UsesVerify]
public class ReportRegressionTests
{
    [Fact]
    public Task GenerateReport_MatchesSnapshot()
    {
        // var result = ReportGenerator.Generate(sampleInput);
        // return Verify(result);
        return Verify("placeholder");
    }
}
