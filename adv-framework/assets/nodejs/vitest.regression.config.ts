import { defineConfig } from 'vitest/config';

// REGRESSION TEST config — run via `vitest run -c vitest.regression.config.ts`
// in the `golden-file-regression` CI job. Only matches *.regression.test.ts.
//
// To intentionally update a snapshot after a verified behavior change:
//   npx vitest run -c vitest.regression.config.ts --update
// That flag is a human decision made locally, never something CI runs
// automatically — same rule as syrupy/Verify/goldie in the other four
// language pipelines.
export default defineConfig({
  test: {
    include: ['**/*.regression.test.ts'],
    exclude: ['**/node_modules/**'],
  },
});
