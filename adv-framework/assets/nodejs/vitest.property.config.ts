import { defineConfig } from 'vitest/config';

// PROPERTY TEST config — run via `vitest run -c vitest.property.config.ts`
// in the `property-test` CI job. Only matches *.property.test.ts, so it
// never overlaps with the default unit run.
export default defineConfig({
  test: {
    include: ['**/*.property.test.ts'],
    exclude: ['**/node_modules/**'],
  },
});
