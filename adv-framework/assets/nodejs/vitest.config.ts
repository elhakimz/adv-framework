import { defineConfig } from 'vitest/config';

// Default config — used by `unit-test` in CI (plain `vitest run`).
// Explicitly excludes the property and regression suites so the
// everyday test run stays fast; they run in their own CI stage via
// their own config files (vitest.property.config.ts, vitest.regression.config.ts).
export default defineConfig({
  test: {
    include: ['**/*.test.ts'],
    exclude: [
      '**/node_modules/**',
      '**/*.property.test.ts',
      '**/*.regression.test.ts',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'cobertura'],
      reportsDirectory: './coverage',
    },
  },
});
