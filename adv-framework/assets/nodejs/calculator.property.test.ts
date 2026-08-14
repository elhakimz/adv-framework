import { describe, it } from 'vitest';
import fc from 'fast-check';

// PROPERTY TEST — the .property.test.ts suffix is what keeps this file
// out of the default `vitest run` (see vitest.config.ts's exclude list).
// It only runs via `vitest run -c vitest.property.config.ts`.
//
// fast-check generates inputs and shrinks any failure to the smallest
// reproducing case, same role as Hypothesis/jqwik/FsCheck/rapid in the
// other four language pipelines.

describe('calculateSomething properties', () => {
  it('is commutative', () => {
    fc.assert(
      fc.property(fc.integer(), fc.integer(), (a, b) => {
        // return calculateSomething(a, b) === calculateSomething(b, a);
        return true;
      }),
    );
  });

  it('never returns a negative result', () => {
    fc.assert(
      fc.property(fc.array(fc.float(), { minLength: 1 }), (values) => {
        // const result = calculateSomething(...values);
        // return result >= 0;
        return true;
      }),
    );
  });
});
