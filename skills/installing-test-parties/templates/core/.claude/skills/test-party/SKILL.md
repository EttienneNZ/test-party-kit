---
name: test-party
description: Run manual QA of {{PLANS_DIR}} cases against {{PRODUCT}} on {{ENVIRONMENT}} as a Test Party, recording Passed/Failed/Blocked results in git. Use when asked to start or continue a test party, run or QA test cases, or end a party.
---

# Test Party

<!-- if:automation -->
You are a QA tester. You drive real, signed-in persona browsers through **{{PRODUCT}}** on
**{{ENVIRONMENT}}** with Playwright MCP, run test cases, and record a result for each. You do
not fix code.
<!-- endif:automation -->
<!-- if:manual -->
You run a QA session with a human tester. The tester drives **{{PRODUCT}}** on
**{{ENVIRONMENT}}** by hand; you pick the cases, walk them through each one step by step,
judge each Expected Result from what they report, and record a result for each. You do not
fix code.
<!-- endif:manual -->
Read [`{{PARTIES_DIR}}/README.md`]({{PARTIES_README_LINK}}) first — it defines Test Party,
Build, Result, stale, and remaining{{AUTOMATION_README_MENTION}}.

`party.py` in this folder does all bookkeeping — joining, reading cases, recording,
<!-- if:automation -->
replaying Case Specs, keeping new ones,
<!-- endif:automation -->
committing, pushing. Run `python3 .claude/skills/test-party/party.py <command> --help` for
arguments. Below, `party.py` means that path.

**A session runs at most {{SESSION_CASES}} cases yourself.** {{SESSION_CONSTRAINT}}; the
party tracks progress, so the next session continues where this one stopped.
<!-- if:automation -->
Automated Cases, which `party.py run` replays, don't count toward the {{SESSION_CASES}}.
<!-- endif:automation -->
The skill takes no arguments — ask for anything you need.

## 1. Join a party

`party.py parties` lists open parties. Ask which to join, or offer to start one: ask for a
name (`<yyyy-mm-dd>-<kebab-name>`) and the features in scope (the `{{PLANS_DIR}}/*.csv`
slugs; default all). `party.py join <party> [--features a,b]` joins it, starting it first if
it doesn't exist.

If the user wants to **end** the party instead, run `status`, show what's still remaining,
and on confirmation open a PR from `{{PARTY_BRANCH_PREFIX}}<party>` to `{{BASE_BRANCH}}`
titled `docs: end test party <party>` with the `status` summary in the body — or, if the
branch already has an open PR, run `party.py pr <party>` and mark it ready for review. Stop
there.

Ask for the tester name — one lowercase word; it names their results log. `tips.local.md` in
this folder (gitignored) holds the tester's personal tips; read it if it exists, and add a tip
there when the tester asks you to remember one.

<!-- if:automation -->
## 2. Profiles and MCP servers

The profiles are `{{E2E_DIR}}/personas.local.ts` (gitignored): the tester name and each
[persona](#personas)'s accounts, port, and fixtures. If it's missing, build it from
`{{E2E_DIR}}/personas.example.ts`, which documents every field:

1. Ask for the tester name.
2. For each persona, ask for its account details. Keep the example's ports and user-data
   dirs unless the tester has a reason to change them.
3. Ask which fixtures exist in each account. Ask the tester to create any that don't before
   you write them in.
4. Show the personas as a table, ask the user to confirm or correct it, and write the file.

Each persona is driven by its own Playwright MCP server named after it, so its tools are
`mcp__<persona>__browser_*`. If any persona has no such tools in this session, register the
missing ones: `npm --prefix {{E2E_DIR}} run --silent mcp` prints each persona's server config, and
for each missing persona run `claude mcp add-json -s local <persona> '<config json>'`. After a
port change, run `claude mcp remove -s local <persona>` first. New servers load only at
startup, so ask the tester to restart Claude Code and run `/test-party` again, and stop.

## 3. Sign in

Check the browsers with `npm --prefix {{E2E_DIR}} run browsers -- --no-wait`. Exit 0 means every
persona is running and signed in; go to step 4. Exit 2 means the profiles are missing or
invalid; go back to step 2.

Otherwise start `npm --prefix {{E2E_DIR}} run browsers` in the background. It opens a headed Chrome
per persona that isn't running, at each persona's sign-in page. Ask the tester to sign in to
every browser, leave them open for the session, and tell you when they're done. When they
confirm, run the `--no-wait` check again and continue once it exits 0.

## 4. Preflight and build

Run `npm --prefix {{E2E_DIR}} run --silent preflight`. It checks the baseline every case starts
from and prints one JSON object to stdout. **On any failure, stop the session and report each
one by persona and check — don't repair it**, because repairing changes what later cases see.
Tell the tester what to fix by hand (sign a persona in, maximise or show its window, close a
stray dialog), then rerun preflight and continue once it passes.

Then pin the **build** for the session: `app_version` from the preflight JSON (or from
`party.py build` when preflight has none), and `deploy_sha` from `party.py build`. Show the
user any warnings `build` prints. If it says a deploy is in progress, wait until it lands and
run `build` again before starting. Every result this session records this build.

This is the **baseline state**. Every case starts from it.

## 5. Run Automated Cases

```bash
party.py run <party> --tester <name> --app-version <v> --deploy-sha <sha>
```

It replays every Automated Case in the whole party, before the tester picks a feature. Show
the user its stdout summary. Each entry in its `failed` list has a `kind`: `product` when the
spec broke judging the product, so its case goes to your queue; `setup` when it broke in the
{{SETUP_LABEL}} helper it names as `helper`, before judging the product, so you repair the
helper in step 6 and leave the case alone; `transient` when {{TRANSIENT_LABEL}} stopped it,
which judges nothing, so leave the case for a later run. If it fails with `preflight failed`,
handle it as in step 4: a new app version means pin the build again; anything else stops the
session. `baseline not restored after <case>` also stops the session.

## 6. Repair setup failures

A `setup` failure means the spec's setup in {{SETUP_LABEL}} broke, usually a locator that no
longer matches. One helper often breaks several specs at once; group them by `helper`. Repair
them before running any case: a spec you write in step 9 replays against the helpers as they
stand. Skip this step when `run` reported no `setup` failure.

1. In the session's spec-branch worktree (`party.py spec-branch`, step 9), find what the
   helper meets now: read its failure [as text](#diagnose-from-text), open its trace
   (`npx playwright show-trace <artifacts>/<persona>-trace.zip`), or drive the same action
   through the persona's MCP server. Fix the helper in `{{HELPERS_DIR}}/`. Fix a spec only if
   the case also has your agent `Passed` on this build.
2. Keep it:

   ```bash
   party.py repair <party> --tester <name> --app-version <v> --deploy-sha <sha>
   ```

   It typechecks, then replays every current spec that uses a changed file, each on its own.
   If all pass, it commits the change to the session's spec PR. A spec a transient refusal
   stops is listed as `unverified` and doesn't block the repair, as long as another spec
   passes; name it in the report. If any fails, it discards every uncommitted change in the
   worktree and prints each failure: read them, fix again, and rerun `repair`. After three
   discarded attempts on one helper, stop and name the helper and its last failures in the
   report.

Repairs don't count toward the {{SESSION_CASES}} cases.
<!-- endif:automation -->
<!-- if:manual -->
## 2. Pin the build

Run `party.py build`. It prints the `app_version` and `deploy_sha` that {{ENVIRONMENT}} is
running{{BUILD_NOTE}}. Show the user any warnings; `gh unavailable` means `gh` isn't installed or
signed in to this repo's GitHub, which the tester can fix. If it says a deploy is in progress, wait
until it lands and run `build` again before starting. If it can't tell (`unknown`), ask the
tester what {{ENVIRONMENT}} runs, or record `unknown`. Every result this session records this
build.

Then ask the tester to confirm the **baseline** every case starts from: {{BASELINE}}.
<!-- endif:manual -->

## {{STEP_PICK}}. Pick the work

Run `party.py status <party> --app-version <v> --deploy-sha <sha>` and show each feature as
`<title> · <n> remaining`{{AUTOMATED_COUNT}}, with its failed and blocked counts. Ask which
feature to run; the user may instead name a scenario or Case IDs (the only way to rerun a
`Blocked` case).

<!-- if:automation -->
Your queue is the `product` cases from `run`'s `failed` list first, then the next remaining
cases in the chosen scope that aren't already queued, in `status` order, up to
**{{SESSION_CASES}} cases in total**. When the user wants spec coverage rather than new
results, add `--unspecced` to `status`: it lists the Passed cases with no current Case Spec on
`{{BASE_BRANCH}}` or any of the party's spec branches.
<!-- endif:automation -->
<!-- if:manual -->
Your queue is the next remaining cases in the chosen scope, in `status` order, up to
**{{SESSION_CASES}} cases**.
<!-- endif:manual -->
Read each with `party.py show <case-id>`.

## {{STEP_RUN}}. Run each case

<!-- if:automation -->
1. **Cast.** Say which persona plays each role before starting, e.g.
   `AB-004: owner = {{FIRST_PERSONA}}, recipient = <persona> (viewer)`. If no persona holds an
   [account fact](#personas) the case needs, record `Blocked` with its note and move on.
2. **Run.** Walk the steps through each persona's MCP server. Check each Expected Result
   against the step number it belongs to, reading it off the page as text: `innerText` or
   `ariaSnapshot()` of the region it names. Look at a picture only for a result text can't
   show (an image, a layout), as `browser_take_screenshot` of that element's `ref`, not the
   viewport. Save a screenshot of any failure for the report with `page.screenshot({ path })`
   in `browser_run_code_unsafe`. For a failing-spec case, read its spec error first: it names
   where the replay stopped.
3. **Record** it — `record` commits, pushes, and refreshes the Current status section of
   the party's PR description; tell the user if it says the description wasn't updated.
   For `Failed`, the note is the step and what you observed; for `Blocked`, the reason.
   A failing-spec case you fail too is a **real failure**: record `Failed`, and keep the
   spec's error and artifacts folder from `run`'s output for the bug draft.

   ```bash
   party.py record <party> <case-id> <result> --method agent --tester <name> \
     --app-version <v> --deploy-sha <sha> --note "<one line>"
   ```

4. **Restore.** If the case changed the baseline, put it back before the next case, and
   rerun preflight. If it fails, stop the session as in step 4.
<!-- endif:automation -->
<!-- if:manual -->
1. **Cast.** Say which account or role the tester plays before starting, e.g.
   `AB-004: tester signs in as the record owner`. If the case needs an account or role the
   tester doesn't have, record `Blocked` with that as the note and move on.
2. **Walk it.** Give the tester the setup and the steps, a few at a time. After each step
   that has an Expected Result, ask what they see and compare it, word for word where the
   case quotes text. Ask for a screenshot when the description leaves doubt. Don't accept "it
   worked" for a result with specifics: ask for the specifics.
3. **Record** it — `record` commits, pushes, and refreshes the Current status section of
   the party's PR description; tell the user if it says the description wasn't updated.
   For `Failed`, the note is the step and what the tester observed; for `Blocked`, the reason.

   ```bash
   party.py record <party> <case-id> <result> --method human --tester <name> \
     --app-version <v> --deploy-sha <sha> --note "<one line>"
   ```

4. **Restore.** If the case changed the baseline (uninstalled, signed out, revoked access,
   changed a setting), ask the tester to put it back before the next case.
<!-- endif:manual -->

<!-- if:automation -->
## 9. Write or repair the Case Spec

After each case you record `Passed`, write its Case Spec, so the next party replays it
instead of you. **Never write one from a `Failed` or `Blocked` run**: a spec of a failure
encodes the bug as expected behaviour, and `keep-spec` refuses it. The same step covers a new
case, a stale spec (the case's text changed), and a broken spec (the spec failed but you
passed). Each gets a spec written fresh from your run, carrying the case's current hash.

1. `party.py spec-branch <party> --tester <name>` prints the worktree of this session's Case
   Spec branch, off `{{BASE_BRANCH}}`, creating it on first use. Write every spec and helper
   change there, never in the party worktree or the user's working copy.
2. Write `{{SPECS_DIR}}/<feature>/<case-id>.spec.ts` in that worktree from what you just did,
   following [Writing a Case Spec]({{E2E_README_LINK}}#writing-a-case-spec). For a broken or
   stale spec, rewrite the existing file.
3. Keep it:

   ```bash
   party.py keep-spec <party> <case-id> --tester <name> --app-version <v> --deploy-sha <sha>
   ```

   It acts only on the spec and the changed helpers it imports, so specs you've written
   ahead wait in the worktree for their own `keep-spec`. It typechecks, replays the spec once
   on its own, then every committed spec using a helper you changed. If they pass, it
   commits, pushes, and opens or updates the session's spec PR, printing its URL. If it
   fails, it reverts those files, saves them as a patch, and prints the failure and the patch
   path; `git apply <patch>` in the worktree brings them back. Read the failure
   [as text](#diagnose-from-text), then act on what failed:

   - **A setup helper** (the failure names it): restore the patch, fix the helper as in
     step 6, and rerun `keep-spec`.
   - **An assertion on something you assumed rather than saw**: a name, label or value your
     run never read off the page. Restore the patch, read the real value in the persona
     browser, fix the assertion, and rerun `keep-spec`.
   - **Anything else**: the spec only worked because of state your run left behind. Note the
     case and the failure for the report and move on.

   After three discarded attempts on one spec, report it as step 6 does. If it prints
   `baseline not restored after <case>`, stop the session as in step 4.

Writing and keeping a spec doesn't count toward the {{SESSION_CASES}} cases. If a spec needs a
new test ID in the product, don't write it: the solo replay can't pass until that change is
deployed. Instead, name the case and the ambiguous element in the report.
<!-- endif:automation -->

## {{STEP_REPORT}}. Report

End the session with:

- Each case you ran: result, and for failures the step that failed, expected vs observed.
<!-- if:automation -->
  A failing-spec case you passed means the spec, not the product, is broken — say so.
- The spec PR `keep-spec` or `repair` printed, with the cases it added or rewrote, each
  helper `repair` kept and the specs it replayed, any case whose spec failed its solo replay
  or wasn't written, and any helper you couldn't repair. The PR needs a normal review; its
  specs run in parties only once it merges.
<!-- endif:automation -->
- Blocked cases and why.
- Anything in a case's text that's wrong against the shipped product — the user decides
  whether the case or the product is wrong. A case fix is an ordinary branch off
  `{{BASE_BRANCH}}` using `/write-test-plan`; once merged, it marks that case's results stale.
- A draft bug ticket per distinct bug for {{ISSUE_TRACKER}}{{BUG_CONVENTIONS}}: the case ID,
  the build, the failing step, expected vs observed, and steps to reproduce.
<!-- if:automation -->
  For a real failure, also give the spec's error and its artifacts folder (the screenshot and
  `<persona>-trace.zip`, viewable with `npx playwright show-trace`) as reproducible evidence.
<!-- endif:automation -->
  **Create a ticket only after the user approves that draft.** Triage first: a failure caused
  by stale test copy, environment setup, or a known limitation is not a bug.
- `status` for the feature, with its remaining counts — the next session continues from there.

<!-- if:automation -->
## Personas

Test cases describe accounts in prose ("the owner", "another user", "a viewer"). Two kinds of
fact hide in that prose. **Roles on a record** — owner, editor, viewer — are set up inside a
case by sharing. **Account facts** — sign-in, locale, organisation membership and role — are
set up by the tester between sessions, so each is a fixed persona in its own browser, kept as
preflight found it:

{{PERSONAS_TABLE}}

A case runs only if some persona in the profiles already holds every account fact it needs.
Otherwise record it `Blocked` at cast, before touching any browser:

{{BLOCKED_TABLE}}
<!-- endif:automation -->

## Tips

{{TIPS}}
<!-- if:automation -->
- **Save screenshots under `.playwright-mcp/`**; the MCP servers refuse paths outside the repo.
- <a id="diagnose-from-text"></a>**Diagnose a failure from text.** A failed spec's artifacts
  folder holds `error-context.md` (the error and call log) and `<persona>-snapshot.md`, each
  persona page's aria snapshot when it failed. Grep the snapshot for the locator or the text
  you expected. Open a PNG only when that text can't explain the failure.
- **Popups open as new tabs** in the persona's browser. Switch to it with `browser_tabs`, act
  in it, then switch back. A click that closes the popup may report "page closed"; the click
  still succeeded.
- **Only the front tab renders.** A click or screenshot in a background tab or hidden window
  waits for "visible, enabled and stable" until it times out. Start any
  `browser_run_code_unsafe` that clicks with `await page.bringToFront()`.
- **After a browser restart** the MCP server's current tab may not be the one you expect.
  `browser_tabs select` the right one before acting.
- **Waiting for the tester:** poll every few seconds; a 30s poll misses short-lived screens.
<!-- endif:automation -->
