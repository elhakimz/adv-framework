import { describe, it, expect } from 'bun:test';

// UNIT TEST — lives in tests/unit/, discovered only when CI runs
// `bun test tests/unit`. Directory placement IS the isolation
// mechanism for Bun (see the note at the top of gitlab-ci-bun-adv.yml
// on why file-naming/markers weren't used here instead).

describe('calculateSomething', () => {
  it('returns the expected value for a known case', () => {
    // const result = calculateSomething(10, 5);
    // expect(result).toBe(15);
  });
});
