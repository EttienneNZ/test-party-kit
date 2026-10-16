import { cdpEndpoint } from './browsers.ts';
import { loadPersonas, PersonaError } from './personas.ts';

const PLAYWRIGHT_MCP = '@playwright/mcp@{{PLAYWRIGHT_MCP_VERSION}}';

async function main(): Promise<void> {
  const personas = await loadPersonas();
  const servers = Object.fromEntries(
    personas.map((persona) => [
      persona.name,
      { command: 'npx', args: ['-y', PLAYWRIGHT_MCP, '--cdp-endpoint', cdpEndpoint(persona)] },
    ])
  );
  console.log(JSON.stringify(servers, null, 2));
}

main().catch((error: unknown) => {
  console.error(error instanceof PersonaError ? error.message : error);
  process.exit(2);
});
