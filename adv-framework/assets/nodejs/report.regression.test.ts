import { describe, it, expect } from 'vitest';

// REGRESSION TEST — the .regression.test.ts suffix keeps this out of the
// default `vitest run` (see vitest.config.ts's exclude list). Only runs
// via `vitest run -c vitest.regression.config.ts`.
//
// Vitest's toMatchSnapshot() is built in, no extra library needed —
// compares against a committed __snapshots__ file, same role as
// syrupy/Verify/goldie in the other four language pipelines.

describe('report generation regression', () => {
  it('matches the committed snapshot', () => {
    // const result = generateReport(sampleInput);
    const result = { placeholder: 'output' };
    expect(result).toMatchSnapshot();
  });
});
