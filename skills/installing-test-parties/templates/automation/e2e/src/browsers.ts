import { spawn } from 'node:child_process';
import { chromium, expect, type Browser, type BrowserContext, type Page } from '@playwright/test';
import { PersonaError, type NamedPersona } from './personas.ts';

/** Playwright's default is no limit, so a click a stray dialog intercepts would wait out the whole test. */
const ACTION_TIMEOUT_MS = 30_000;
export const LOAD_TIMEOUT_MS = 60_000;
/**
 * The narrowest page every persona browser keeps. Products change layout below some width, and specs know only the
 * wide one, so preflight fails a narrower window.
 */
export const MIN_PAGE_WIDTH_PX = 1200;
const WINDOW = { width: 1440, height: 1000 };

const CHROME_BY_PLATFORM: Partial<Record<NodeJS.Platform, string>> = {
  darwin: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  linux: 'google-chrome-stable',
  win32: 'chrome',
};

export type SignInState = 'signed-in' | 'signed-out';

export interface PersonaBrowser {
  persona: NamedPersona;
  browser: Browser;
  context: BrowserContext;
}

export function cdpEndpoint(persona: NamedPersona): string {
  return `http://localhost:${persona.port}`;
}

export async function isRunning(persona: NamedPersona): Promise<boolean> {
  try {
    const response = await fetch(`${cdpEndpoint(persona)}/json/version`, { signal: AbortSignal.timeout(2000) });
    return response.ok;
  } catch {
    return false;
  }
}

/** Starts Chrome detached, so it outlives the launcher. Chrome refuses remote debugging on the default profile, hence the user-data dir. */
export function launchChrome(persona: NamedPersona): void {
  const chrome = process.env.CHROME_PATH ?? CHROME_BY_PLATFORM[process.platform];
  if (!chrome) throw new PersonaError(`No Chrome known for ${process.platform}; set CHROME_PATH.`);
  const args = [
    `--remote-debugging-port=${persona.port}`,
    `--user-data-dir=${persona.absoluteUserDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    // Desktop text scaling otherwise raises the device pixel ratio, shrinking the page inside the window.
    '--force-device-scale-factor=1',
    `--window-size=${WINDOW.width},${WINDOW.height}`,
    ...persona.signInUrls,
  ];
  spawn(chrome, args, { detached: true, stdio: 'ignore' }).unref();
}

export async function attach(persona: NamedPersona): Promise<PersonaBrowser> {
  if (!(await isRunning(persona))) {
    throw new PersonaError(
      `Persona ${persona.name}: no browser on port ${persona.port}. Run \`npm --prefix e2e run browsers\` and sign in.`
    );
  }
  const browser = await chromium.connectOverCDP(cdpEndpoint(persona));
  const context = browser.contexts()[0];
  context.setDefaultTimeout(ACTION_TIMEOUT_MS);
  context.setDefaultNavigationTimeout(LOAD_TIMEOUT_MS);
  return { persona, browser, context };
}

function isHome(persona: NamedPersona, page: Page): boolean {
  try {
    return new URL(page.url()).host === new URL(persona.homeUrl).host;
  } catch {
    return false;
  }
}

function isSignedOut(persona: NamedPersona, page: Page): boolean {
  return new RegExp(persona.signedOutUrl).test(page.url());
}

/** Read from the persona's open tabs without navigating them, for the launcher's report. */
export function signInState({ persona, context }: PersonaBrowser): SignInState {
  const home = context.pages().filter((p) => isHome(persona, p));
  return home.some((p) => !isSignedOut(persona, p)) ? 'signed-in' : 'signed-out';
}

/** The persona's home tab, reused if open, and whether it's signed in. */
export async function homeTab(attached: PersonaBrowser): Promise<{ page: Page; state: SignInState }> {
  const { persona, context } = attached;
  let page = context.pages().find((p) => isHome(persona, p));
  if (!page) {
    page = await context.newPage();
    await page.goto(persona.homeUrl);
  }
  return { page, state: isSignedOut(persona, page) ? 'signed-out' : 'signed-in' };
}

/** Names of the dialogs open over a page. An open dialog usually intercepts clicks on everything behind it. */
export async function openDialogs(page: Page): Promise<string[]> {
  const dialogs = await page.getByRole('dialog').or(page.getByRole('alertdialog')).filter({ visible: true }).all();
  return Promise.all(
    dialogs.map(async (dialog) => {
      const named = /dialog "(.+?)"/.exec(await dialog.ariaSnapshot());
      return named ? named[1] : (await dialog.innerText()).trim().split('\n')[0];
    })
  );
}

/** Closes every dialog open over a page with Escape, one at a time. */
export async function closeDialogs(page: Page): Promise<void> {
  for (let open = (await openDialogs(page)).length; open > 0; open--) {
    await page.keyboard.press('Escape');
    await expect.poll(async () => (await openDialogs(page)).length).toBeLessThan(open);
  }
}

export function pageWidth(page: Page): Promise<number> {
  return page.evaluate(() => window.innerWidth);
}

/** Whether the page paints: Chrome stops painting a minimised window or one on a hidden workspace, and every click in it then times out. */
export async function renders(page: Page): Promise<boolean> {
  return page
    .evaluate(() => new Promise<boolean>((done) => {
      requestAnimationFrame(() => done(true));
      setTimeout(() => done(false), 2000);
    }))
    .catch(() => false);
}
