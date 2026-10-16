import { writeFile } from 'node:fs/promises';
import { test as base, type Page } from '@playwright/test';
import { attach, closeDialogs, homeTab, type PersonaBrowser } from './browsers.ts';
import { loadPersona, PersonaError } from './personas.ts';

export { expect } from '@playwright/test';

export interface PersonaSession extends PersonaBrowser {
  /** The persona's own home tab, reused rather than opened fresh. */
  page: Page;
}

export interface Personas {
  get(name: string): Promise<PersonaSession>;
}

/**
 * Marks a test as the Case Spec for one Test Case; `npm run cases` reads these without running anything.
 * `party.py run` reads the arguments from the source on the base branch, so pass them as literals.
 * `changesBaseline` makes it rerun preflight after this spec, to check the spec's teardown restored the baseline.
 */
export function caseSpec(caseId: string, caseHash: string, { changesBaseline = false } = {}) {
  return {
    annotation: [
      { type: 'case_id', description: caseId },
      { type: 'case_hash', description: caseHash },
      ...(changesBaseline ? [{ type: 'changes_baseline' }] : []),
    ],
  };
}

export const test = base.extend<{ personas: Personas }>({
  // eslint-disable-next-line no-empty-pattern -- Playwright reads fixture dependencies from this destructuring
  personas: async ({}, use, testInfo) => {
    const sessions = new Map<string, { session: PersonaSession; pagesBefore: Set<Page> }>();

    async function open(name: string): Promise<PersonaSession> {
      const attached = await attach(await loadPersona(name));
      const pagesBefore = new Set(attached.context.pages());
      const { page, state } = await homeTab(attached);
      if (state === 'signed-out') {
        await attached.browser.close();
        throw new PersonaError(`Persona ${name} has fallen back to a sign-in page. Sign in again in its browser.`);
      }
      await page.bringToFront();
      await attached.context.tracing.start({ screenshots: true, snapshots: true });
      const session = { ...attached, page };
      sessions.set(name, { session, pagesBefore });
      return session;
    }

    await use({ get: async (name) => sessions.get(name)?.session ?? open(name) });

    const failed = testInfo.status !== testInfo.expectedStatus;
    for (const [name, { session, pagesBefore }] of sessions) {
      if (failed) {
        await writeSnapshot(session.page, testInfo.outputPath(`${name}-snapshot.md`)).catch(() => undefined);
        await session.page.screenshot({ path: testInfo.outputPath(`${name}.png`) }).catch(() => undefined);
        await session.context.tracing.stop({ path: testInfo.outputPath(`${name}-trace.zip`) });
        // A spec that fails mid-dialog can't close it, and the open dialog would then fail every later spec.
        await closeDialogs(session.page).catch(() => undefined);
      } else {
        await session.context.tracing.stop();
      }
      const leftover = session.context.pages().filter((p) => !pagesBefore.has(p));
      await Promise.all(leftover.map((p) => p.close()));
      await session.browser.close();
    }
  },
});

/** A persona page is attached over CDP, so Playwright's own error-context.md has no snapshot of it. */
async function writeSnapshot(page: Page, path: string): Promise<void> {
  const sections = [`# ${await page.title()}\n\n${page.url()}\n\n${await page.locator('body').ariaSnapshot()}`];
  for (const frame of page.frames()) {
    if (frame === page.mainFrame() || !frame.url().startsWith('http')) continue;
    const snapshot = await frame
      .locator('body')
      .ariaSnapshot()
      .catch((error: Error) => `(no snapshot: ${error.message})`);
    sections.push(`# Frame ${frame.url()}\n\n${snapshot}`);
  }
  await writeFile(path, sections.join('\n\n'));
}
