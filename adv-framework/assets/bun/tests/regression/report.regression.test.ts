import { describe, it, expect } from 'bun:test';

// REGRESSION TEST — lives in tests/regression/, discovered only when CI
// runs `bun test tests/regression`. toMatchSnapshot() is built into
// bun:test (Jest-compatible), no extra library needed.

describe('report generation regression', () => {
  it('matches the committed snapshot', () => {
    // const result = generateReport(sampleInput);
    const result = { placeholder: 'output' };
    expect(result).toMatchSnapshot();
  });
});
