import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export const E2E_DIR = resolve(import.meta.dirname, '..');
const LOCAL_FILE = resolve(E2E_DIR, 'personas.local.ts');

export interface Persona {
  /** Chrome's remote-debugging port. Specs and this persona's Playwright MCP server attach here. Unique per persona. */
  port: number;
  /** Chrome profile, relative to e2e/. Keep it under the gitignored .browsers/: it holds live session cookies. */
  userDataDir: string;
  /** Opened when the launcher starts this persona's browser, for the tester to sign in. */
  signInUrls: string[];
  /** The tab specs act in, reused if open. */
  homeUrl: string;
  /** A regex for the URLs the home tab lands on when signed out. */
  signedOutUrl: string;
  /** Account facts preflight and specs can read: emails, organisation, role, locale. */
  account?: Record<string, string | null>;
  /** Named data that must exist in this persona's accounts for the cases that rely on it. */
  fixtures?: Record<string, unknown>;
}

export interface PersonaFile {
  tester: string;
  personas: Record<string, Persona>;
}

export interface NamedPersona extends Persona {
  name: string;
  absoluteUserDataDir: string;
}

export class PersonaError extends Error {}

export async function loadPersonas(): Promise<NamedPersona[]> {
  if (!existsSync(LOCAL_FILE)) {
    throw new PersonaError('No e2e/personas.local.ts. Copy e2e/personas.example.ts to it and fill in your accounts.');
  }
  const file: PersonaFile = (await import(pathToFileURL(LOCAL_FILE).href)).default;
  return Object.entries(file.personas).map(([name, persona]) => ({
    ...persona,
    name,
    absoluteUserDataDir: resolve(E2E_DIR, persona.userDataDir),
  }));
}

export async function loadPersona(name: string): Promise<NamedPersona> {
  const personas = await loadPersonas();
  const persona = personas.find((p) => p.name === name);
  if (!persona) {
    throw new PersonaError(
      `Persona ${name} isn't in e2e/personas.local.ts (it has ${personas.map((p) => p.name).join(', ')}).`
    );
  }
  return persona;
}
