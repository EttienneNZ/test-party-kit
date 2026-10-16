---
name: installing-test-parties
description: Use when setting up manual QA test plans and Test Parties in a repository, porting the write-test-plan and test-party skills and party.py to another repo, or upgrading an existing party.py install.
---

# Installing Test Parties

Installs two repo skills and their bookkeeping script into a target git repo:

- **`/write-test-plan`** — turns stories and acceptance criteria into journey-shaped CSV test
  cases in `<plans_dir>/`.
- **`/test-party`** — runs those cases as a Test Party: results logged per tester on a party
  branch, keyed to the build and to a hash of each case's text, so a reworded case goes stale.
- **`party.py`** — the only writer of results. Generic, tested, configured by
  `.claude/skills/test-party/test-party.json`.

Two modes. **Manual** (default): a human tester drives the product, the agent picks cases,
walks them step by step, and records. **Automation** (opt-in): adds an `e2e/` Playwright
workspace with signed-in persona browsers, preflight, an agent driving them over Playwright
MCP, and Case Specs that `party.py run` replays so passed cases stop costing a person's time.

Everything mechanical is in `install.py`. Your job is the survey, the interview, and checking
the result.

## 1. Survey the target repo

Answer what you can from the repo before asking anything:

| Answer | Where to look |
| --- | --- |
| `remote`, `base_branch` | `git remote`; `git ls-remote --symref origin HEAD` (works when `origin/HEAD` was never set) |
| `build` | `.github/workflows/*deploy*`: a workflow that deploys the test environment → `github_deploy`. `title_contains` is a substring of the run's displayed title (work it out from `run-name`, including what a push renders) that only test-environment deploys have; `branch` is the branch they should deploy, default `base_branch`. Otherwise a script that prints the version → `command`. Neither → `{}` |
| `commit_env` | A pre-commit hook configured in the repo, installed in this checkout or not, that can't run in a worktree under `.git/` (husky running tests → `{"HUSKY": "0"}`; lefthook → `{"LEFTHOOK": "0"}`) |
| `glossary`, `limitations` | Files like `GLOSSARY.md`, `CONTEXT.md`, `LIMITATIONS.md`, `docs/adr/` |
| `issue_tracker`, `bug_conventions` | `CLAUDE.md`, `AGENTS.md`, `docs/agents/`, ticket keys in branch names and commits |
| `plans_dir`, `parties_dir` | Existing QA docs; otherwise keep `docs/test-plans`, `docs/test-parties` |
| `ci_check` | A CI workflow you could add a step to. `true` means you add the step in step 5 |
| Code host | `git remote -v` on GitHub, and `gh auth status`. Party PRs, PR status refresh and `github_deploy` need both; without them results still record and push, and you tell the user what degrades |
| Automation fit | A web UI the tester signs in to; Node 23.6+; Chrome installed |

If the repo already has `.claude/skills/test-party/` or `.claude/skills/write-test-plan/`,
go to [Upgrading](#upgrading) instead.

## 2. Interview for the rest

Ask only what the survey couldn't settle, a few questions at a time:

1. **Product and environment** — what's under test, where testers run it (`staging`), and its
   URL.
2. **Mode** — manual, or automation too. Recommend manual unless the product is a web UI and
   the team wants passed cases replayed.
3. **Baseline** — the state every case starts from, in one sentence: who's signed in where,
   what's installed, which settings are at default.
4. **Issue tracker** — confirm the one the survey found, or ask where bugs go and how to reach
   it (an MCP server, `gh`, a URL).
5. **Automation only** — the personas: one per account fact a case can need (a member, an
   admin, a user outside the org). For each: what its browser holds, its sign-in and home URLs,
   and the URL pattern of its sign-in page. The cases that need an account no persona has go in
   `blocked`. `setup_helpers` and `transient_errors` can stay empty until a party finds them.

Every field and its default is in [answers.md](answers.md).

## 3. Install

Write the answers to a JSON file in your scratchpad, not the repo, and dry-run it:

```bash
python3 <this skill>/install.py --dry-run <repo> <answers.json>
```

It prints the files it would write, which already exist, and the lines it appends to
`.gitignore`. Show the user the answers (marking the ones you inferred) and that list, and on
their go-ahead:

```bash
python3 <this skill>/install.py <repo> <answers.json>
```

It renders every template in memory and writes nothing if a placeholder is unanswered or a
file already exists. On success it runs `party.py config` and `party.py check` in the repo.

## 4. Verify

```bash
python3 -m unittest discover -s .claude/skills/test-party
```

All tests must pass (about three minutes; they build throwaway repos). Then `party.py build`:
check it names the build you expect. `gh unavailable` means `gh` isn't installed or signed in
for this repo; otherwise tell the user results will record `unknown` until a build source is
configured.

Automation also: `npm --prefix e2e install`, `npm --prefix e2e run --silent typecheck`, and
`npm --prefix e2e run --silent cases` (prints `[]`). Point the user at `e2e/src/checks.ts`,
where product-specific preflight checks go (right account, app installed, app version).

## 5. Wire up and report

- `ci_check`: add a step running `python3 .claude/skills/test-party/party.py check` after the
  checkout in a job that runs on pull requests. It needs only `python3` and the working tree.
- Add the two skills and `party.py` to the repo's `CLAUDE.md` or `AGENTS.md` if it lists
  skills or commands.
- Report what was written, every answer you inferred rather than asked, and next steps:
  `/write-test-plan` for the first feature, then `/test-party` to start a party.
- Commit only when the user asks, on a branch.

## Upgrading

`party.py` and `test_party.py` are the same in every repo; their behaviour is in
`test-party.json`. To upgrade an install, copy just those two files from
`templates/core/.claude/skills/test-party/` and rerun the unittest suite. Use `--force` only
to regenerate everything: it overwrites the skills' `SKILL.md` files and any local edits in
them.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Asking the user what the repo already says | Survey first; report inferred answers instead |
| Setting `commit_env` blind | Only for a hook you found; a wrong one silently skips the team's checks on party commits |
| Picking automation for a product without a sign-in web UI | Manual mode; automation assumes Playwright against Chrome |
| One persona per test role | Personas are account facts. Roles on a record (owner, viewer) are set up inside a case |
| Editing a rendered `SKILL.md` and then reinstalling with `--force` | Upgrade by copying `party.py` only |
