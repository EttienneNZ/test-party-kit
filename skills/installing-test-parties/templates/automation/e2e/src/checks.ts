import type { Page } from '@playwright/test';
import type { PersonaBrowser } from './browsers.ts';

export interface ProductCheckResult {
  failures: { check: string; message: string }[];
  /** The version of the product under test, if this persona's page can read it. The first one found is the build's. */
  appVersion?: string;
}

/**
 * Product-specific baseline checks, run by preflight on each persona's signed-in home tab after the generic checks
 * pass. Add what every case assumes about this persona: the right account signed in, the app installed and
 * connected, a setting at its default. Never repair anything here; report it, so the tester fixes it by hand.
 * Prefer checks in a tab you open and close, so the tester's and MCP servers' tabs stay where they were.
 */
export async function productChecks(attached: PersonaBrowser, home: Page): Promise<ProductCheckResult> {
  void attached;
  void home;
  return { failures: [] };
}
