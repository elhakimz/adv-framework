import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';

// Flat config (ESLint 9+). Extend with framework-specific configs
// (eslint-plugin-react, etc.) as needed for your project.
export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      // Start conservative — tighten once the codebase is clean enough
      // to make more rules build-breaking without a large one-time fix
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': 'error',
    },
  },
  {
    ignores: ['dist/**', 'coverage/**', 'node_modules/**'],
  },
);
