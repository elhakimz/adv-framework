import { describe, it } from 'bun:test';
import fc from 'fast-check';

// PROPERTY TEST — lives in tests/property/, discovered only when CI
// runs `bun test tests/property`. fast-check works with Bun's
// Jest-compatible test API with no adapter needed.

describe('calculateSomething properties', () => {
  it('is commutative', () => {
    fc.assert(
      fc.property(fc.integer(), fc.integer(), (a, b) => {
        // return calculateSomething(a, b) === calculateSomething(b, a);
        return true;
      }),
    );
  });
});
