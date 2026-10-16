import { defineConfig } from '@playwright/test';

/** Specs attach to the persona browsers the tester signed in to (`npm run browsers`); nothing here launches one. */
export default defineConfig({
  testDir: './specs',
  outputDir: './test-results',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 5 * 60_000,
  expect: { timeout: 15_000 },
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
});
