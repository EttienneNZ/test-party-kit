# e2e

Case Specs: Playwright replays of [Test Cases]({{PARTIES_README_FROM_E2E}}) against
{{ENVIRONMENT}}. They run in persona browsers you sign in to by hand, so no spec stores a
password or a saved session.

## Run

Needs Node 23.6+ (it runs the `.ts` sources directly) and Google Chrome.

1. `npm --prefix e2e ci`.
2. Copy `personas.example.ts` to `personas.local.ts` and fill in your accounts.
3. `npm --prefix e2e run browsers` opens a headed Chrome per persona at its sign-in pages.
   Sign in to each; the launcher reports when every persona is signed in. Leave the browsers
   open for the session. Set `CHROME_PATH` if Chrome isn't at the usual place.
4. `npm --prefix e2e run --silent preflight` checks the baseline every Test Case starts from.
5. `npm --prefix e2e run specs` replays every Case Spec; `-- AB-011` replays one. Failures
   leave an aria snapshot (`<persona>-snapshot.md`), screenshot and trace per persona in
   `test-results/`.

## Preflight

Preflight checks, without changing anything, that every persona's browser is running on its
port, painting (Chrome stops painting a minimised or hidden window, and every click then times
out), signed in, at least `MIN_PAGE_WIDTH_PX` wide (`src/browsers.ts`), and with no dialog
open in its home tab. Then it runs `productChecks` in `src/checks.ts`: the product's own
baseline (right account, app installed, settings at default), and the app version if a page
can read it.

It prints progress to stderr and one JSON object to stdout, which `party.py` parses:

```json
{ "ok": false, "app_version": "1.4.0", "failures": [{ "check": "signed-in", "persona": "member", "message": "…" }] }
```

It exits 0 when every check passes, 1 when any fails, and 2 when it can't run. Preflight
never repairs a failure: repairing changes what later cases see.

## Playwright MCP

An agent drives the same browsers with one Playwright MCP server per persona, named after the
persona and attached to its port. `npm --prefix e2e run --silent mcp` prints each server's
config; register one with `claude mcp add-json -s local <persona> '<config>'` and restart
Claude Code. The `/test-party` skill does this for you. An MCP server and a spec run can use a
browser one after the other, in either order.

## Writing a Case Spec

One file per Case ID at `specs/<feature>/<case-id>.spec.ts`, where `<feature>` is the test
plan's CSV slug.

- **Shape.** Mark the test with `caseSpec(caseId, caseHash)` so `npm run cases` and
  `party.py` can find it. `party.py show <case-id>` prints the marker with the case's current
  hash. Each case step is a `test.step` named with the step's number and text, and each
  Expected Result is an assertion inside the step it belongs to.
- **Helpers.** Get personas from the `personas` fixture and named data from their `fixtures`
  in `personas.local.ts`. When a spec needs DOM handling that isn't in `src/` yet, add a
  helper rather than handle it in the spec. Helpers that drive a third-party system during
  setup go in files matching `setup_helpers` in `test-party.json`{{SETUP_HELPERS_NOTE}}, so a
  failure there is reported as a setup failure, not a product one.
- **Locators.** Prefer role and text. Add a test ID to the product only where role and text
  are ambiguous, in the same PR as the spec that needs it.
- **Baseline-changing specs** (uninstall, sign out, revoke access, change a setting) restore
  the baseline in `test.afterEach`, which runs even when the test fails. They also pass
  `{ changesBaseline: true }` to `caseSpec`, so a party run reruns preflight after them.
- **Unique data.** Put a per-run unique string in whatever a spec creates or sends, so it finds
  its own result and not one left by an earlier run. Don't add sleeps; wait on what you expect.
- **Not generated.** Specs are written from an agent's own run of the case.

```ts
import { caseSpec, expect, test } from '../../src/fixtures.ts';

test('AB-004 owner shares a record with a viewer', caseSpec('AB-004', '0123456789ab'), async ({ personas }) => {
  const { page } = await personas.get('{{FIRST_PERSONA}}');
  const title = `QA share ${Date.now()}`;

  await test.step('1. Create a record', async () => {
    await page.getByRole('button', { name: 'New record' }).click();
    await page.getByLabel('Title').fill(title);
    await page.getByRole('button', { name: 'Save' }).click();
  });

  await test.step('2. Open Share', async () => {
    await page.getByRole('button', { name: 'Share' }).click();
    await expect(page.getByRole('dialog', { name: 'Share' })).toBeVisible();
  });
});
```

## In a Test Party

`party.py run` replays the party's Automated Cases. It reads Case Specs from the base branch,
finding each one's `caseSpec(...)` arguments in its source, so pass them as literals. It runs
them one at a time from your working copy, and skips any spec whose file there differs from
the base branch. Pull first.

Each failing spec has a `kind`: `setup` when it broke in a setup helper, before judging the
product; `transient` when an error matching `transient_errors` stopped it, which judges
nothing; `product` otherwise. New and rewritten specs reach the base branch through a Case
Spec branch: `party.py spec-branch` gives the session a worktree, and `party.py keep-spec`
replays a spec there on its own before committing it and opening or updating the session's
PR. `party.py repair` keeps a helper fix the same way, once every current spec that imports
it passes a solo replay.
