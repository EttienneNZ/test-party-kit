import { setTimeout as sleep } from 'node:timers/promises';
import { attach, isRunning, launchChrome, signInState } from './browsers.ts';
import { loadPersonas, PersonaError, type NamedPersona } from './personas.ts';

const USAGE = `Usage: npm --prefix e2e run browsers -- [persona...] [--no-wait]

Opens a headed Chrome per persona (or reuses one already running on its port), then
waits for you to sign in and reports which personas are signed in. --no-wait reports
once and exits: status 0 when every persona is signed in, 1 otherwise.`;

const SIGN_IN_TIMEOUT_MS = 15 * 60_000;
const POLL_MS = 3000;

async function waitUntilRunning(persona: NamedPersona): Promise<void> {
  for (let attempt = 0; attempt < 30; attempt++) {
    if (await isRunning(persona)) return;
    await sleep(500);
  }
  throw new PersonaError(`Persona ${persona.name}: Chrome didn't open port ${persona.port}.`);
}

async function main(): Promise<number> {
  const args = process.argv.slice(2);
  if (args.includes('--help')) {
    console.log(USAGE);
    return 0;
  }
  const wait = !args.includes('--no-wait');
  const names = args.filter((a) => !a.startsWith('--'));
  const all = await loadPersonas();
  const unknown = names.filter((n) => !all.some((p) => p.name === n));
  if (unknown.length) throw new PersonaError(`Unknown persona: ${unknown.join(', ')}`);
  const personas = names.length ? all.filter((p) => names.includes(p.name)) : all;

  for (const persona of personas) {
    if (await isRunning(persona)) {
      console.log(`${persona.name}: already running on port ${persona.port}`);
    } else if (wait) {
      launchChrome(persona);
      await waitUntilRunning(persona);
      console.log(`${persona.name}: opened on port ${persona.port}`);
    } else {
      console.log(`${persona.name}: not running`);
    }
  }

  const running = [];
  for (const persona of personas) {
    if (await isRunning(persona)) running.push(await attach(persona));
  }
  const allRunning = running.length === personas.length;

  if (wait) console.log('\nSign in to each browser; this waits until every persona is signed in.');
  const deadline = Date.now() + SIGN_IN_TIMEOUT_MS;
  let previous = '';
  try {
    for (;;) {
      const states = running.map((attached) => ({ name: attached.persona.name, state: signInState(attached) }));
      const text = states.map((s) => `${s.name.padEnd(12)} ${s.state}`).join('\n');
      if (text !== previous) console.log(`\n${text}`);
      previous = text;
      if (allRunning && states.every((s) => s.state === 'signed-in')) {
        console.log('\nAll personas signed in.');
        return 0;
      }
      if (!wait || Date.now() > deadline) return 1;
      await sleep(POLL_MS);
    }
  } finally {
    await Promise.all(running.map(({ browser }) => browser.close()));
  }
}

main().then(
  (status) => process.exit(status),
  (error) => {
    console.error(error instanceof PersonaError ? error.message : error);
    process.exit(2);
  }
);
