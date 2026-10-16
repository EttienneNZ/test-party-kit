import {
  attach,
  homeTab,
  isRunning,
  MIN_PAGE_WIDTH_PX,
  openDialogs,
  pageWidth,
  renders,
  type PersonaBrowser,
} from './browsers.ts';
import { productChecks } from './checks.ts';
import { loadPersonas, PersonaError, type NamedPersona } from './personas.ts';

const USAGE = `Usage: npm --prefix e2e run --silent preflight

Checks the Test Party baseline in the running persona browsers, without changing anything:
every browser is running, painting, and signed in, with no dialog open in the tab specs use
and a window at least ${MIN_PAGE_WIDTH_PX}px wide, then the product checks in src/checks.ts.

Prints progress to stderr and one JSON object to stdout:
  {"ok": true, "app_version": "1.2.3", "failures": []}
Each failure is {"check", "persona", "message"}. Exits 0 when every check passes, 1 when
any fails, 2 when it couldn't run (no personas.local.ts).`;

interface Failure {
  check: string;
  persona: string;
  message: string;
}

async function checkPersona(persona: NamedPersona): Promise<{ failures: Failure[]; appVersion?: string }> {
  const fail = (check: string, message: string) => ({ failures: [{ check, persona: persona.name, message }] });
  if (!(await isRunning(persona))) {
    return fail('browser-running', `no browser on port ${persona.port}; run \`npm --prefix e2e run browsers\``);
  }
  let attached: PersonaBrowser | undefined;
  try {
    attached = await attach(persona);
    const { page, state } = await homeTab(attached);
    if (state === 'signed-out') return fail('signed-in', `${page.url()} is a sign-in page; sign in again`);
    if (!(await renders(page))) return fail('renders', 'the window is not painting; un-minimise it or show its workspace');
    const width = await pageWidth(page);
    if (width < MIN_PAGE_WIDTH_PX) return fail('window-width', `page is ${width}px wide; widen it to ${MIN_PAGE_WIDTH_PX}px+`);
    const dialogs = await openDialogs(page);
    if (dialogs.length) return fail('home-tab-clear', `dialog open in the home tab: ${dialogs.join(', ')}`);
    const product = await productChecks(attached, page);
    return {
      failures: product.failures.map((f) => ({ ...f, persona: persona.name })),
      appVersion: product.appVersion,
    };
  } catch (error) {
    return fail('error', error instanceof Error ? error.message.split('\n')[0] : String(error));
  } finally {
    await attached?.browser.close();
  }
}

async function main(): Promise<number> {
  if (process.argv.includes('--help')) {
    console.log(USAGE);
    return 0;
  }
  const personas = await loadPersonas();
  const failures: Failure[] = [];
  let appVersion: string | undefined;
  for (const persona of personas) {
    console.error(`checking ${persona.name}`);
    const result = await checkPersona(persona);
    failures.push(...result.failures);
    appVersion ??= result.appVersion;
  }
  for (const f of failures) console.error(`  ${f.persona} ${f.check}: ${f.message}`);
  console.log(JSON.stringify({ ok: failures.length === 0, app_version: appVersion ?? null, failures }));
  return failures.length ? 1 : 0;
}

main().then(
  (status) => process.exit(status),
  (error) => {
    console.error(error instanceof PersonaError ? error.message : error);
    process.exit(2);
  }
);
