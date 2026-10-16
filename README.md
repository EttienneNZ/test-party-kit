# test-party-kit

A Claude Code plugin that sets up **manual QA test plans** and **git-tracked Test Parties** in
any repository. It has one skill, `installing-test-parties`. You run it once per repo, and it
installs three things into that repo:

| Installed into the repo | What it does |
| --- | --- |
| `/write-test-plan` skill | Turns stories and acceptance criteria into CSV test cases under `docs/test-plans/`. Each row is a *journey*: one sitting at the keyboard with numbered steps, and an expected result tied to each step. |
| `/test-party` skill | Runs those cases as a **Test Party**, a round of QA across chosen features. Results go per tester to a party branch, keyed to the build under test and to a hash of each case's text, so rewording a case marks its old results stale. |
| `party.py` | The bookkeeping script both skills use, and the only writer of results. It handles joining, recording, status, PR status tables and validating plans. Python 3 standard library only, with its own test suite. |

## Two modes

- **Manual** (default). A person runs each case in the product. Claude picks the next cases,
  walks the tester through them step by step, judges each expected result from what the
  tester reports, and records the result. This works for any product, web or not.
- **Automation** (opt-in, web apps). This also adds an `e2e/` Playwright workspace. It
  provides one signed-in Chrome per persona (member, admin, outsider…), a preflight that checks
  the baseline before every session, and Playwright MCP servers so Claude drives the browsers
  itself. It also adds **Case Specs**: once Claude passes a case, it writes a spec, and later
  parties replay it with `party.py run` instead of spending anyone's time.

## Requirements

- Claude Code
- Python 3.9+ and git in the target repo
- The [GitHub CLI](https://cli.github.com/) (`gh`), signed in, for party PRs and their status
  tables, and for reading the deployed build from a GitHub Actions deploy workflow. Without it,
  results still record and push.
- Automation mode only: Node 23.6+ and Google Chrome

## Install the plugin

This repo is both a Claude Code plugin and its own marketplace. You need read access to it.

> Until it's transferred into `Entelect-Australasia`, this repo lives at
> `EttienneNZ/test-party-kit`; use that path in the first command below.

```bash
claude plugin marketplace add Entelect-Australasia/test-party-kit
```

```bash
claude plugin install test-party-kit@test-party-kit
```

Restart Claude Code. The skill shows up as `test-party-kit:installing-test-parties`.

To update later:

```bash
claude plugin marketplace update test-party-kit
```

**Without the plugin system:** clone this repo and copy (or symlink)
`skills/installing-test-parties` into `~/.claude/skills/`.

## Set up a repo

Open Claude Code in the repo you want to set up and ask:

> Set up test parties in this repo

Claude then:

1. **Surveys** the repo for what it can settle itself: the base branch, a deploy workflow to
   read the build from, pre-commit hooks that party commits must skip, a glossary, the issue
   tracker, CI, and whether `gh` works.
2. **Asks** only for the rest: the product and environment (e.g. `staging` and its URL),
   manual or automation mode, the *baseline* every case starts from, and for automation, one
   persona per kind of account a case can need.
3. **Dry-runs** the install and shows you every answer (marking which it inferred), the
   files it will write, and the `.gitignore` lines it will add. Nothing is written until you
   agree, and it never overwrites existing files unless told to.
4. **Installs** and **verifies**: `party.py check`, the `party.py` test suite (about 3
   minutes), `party.py build`, and for automation the e2e typecheck.
5. Optionally adds a CI step that validates the plans on every PR.

Nothing is committed unless you ask.

### What lands in the repo

```
.claude/skills/write-test-plan/SKILL.md
.claude/skills/test-party/SKILL.md
.claude/skills/test-party/party.py          # same file in every repo
.claude/skills/test-party/test_party.py     # its tests
.claude/skills/test-party/test-party.json   # this repo's settings
docs/test-plans/                            # one CSV per feature
docs/test-parties/README.md                 # vocabulary and layout for testers
e2e/                                        # automation mode only
```

## Use it day to day

**Write cases.** Run `/write-test-plan` with a ticket key, a feature name, or nothing (it uses
the current branch's ticket). It builds a coverage ledger from the user stories and acceptance
criteria, cuts it into 4–10 step journeys, writes or updates `docs/test-plans/<feature>.csv`,
and reports any criteria it excluded and why.

**Run a party.** Run `/test-party`. Claude lists the open parties, or starts one
(`2026-10-16-release-qa`, with all features or a chosen few), and pins the build. It then
shows what's remaining per feature and runs up to five cases a session, recording each as
`Passed`, `Failed` (with the step and what was seen) or `Blocked` (with the reason). Every
result is committed and pushed at once, and the party's PR description keeps a live status
table. Next session it picks up where the last one stopped.

**End a party.** Run `/test-party` and say you want to end it. Claude shows what's still
remaining, then opens the party PR to the base branch, or marks it ready.

**Bugs.** At the end of a session Claude drafts one ticket per distinct failure for your
tracker. It files only the drafts you approve.

**Useful `party.py` commands** (`python3 .claude/skills/test-party/party.py <command>`):

| Command | Does |
| --- | --- |
| `parties` | List open parties |
| `status <party>` | Counts per feature and the remaining cases |
| `show <case-id>` | Print a case as it is on the base branch |
| `record <party> <case-id> <result> …` | Append one result, commit, push |
| `check` | Validate the plan CSVs (5 columns, unique IDs); good for CI |
| `build` | What the environment under test is running |
| `config` | The effective `test-party.json` |
| `run`, `spec-branch`, `keep-spec`, `repair` | Automation mode: replay, write and maintain Case Specs |

## Configuration

`party.py` reads `.claude/skills/test-party/test-party.json` in the target repo. The skill
writes it from your answers, and [`answers.md`](skills/installing-test-parties/answers.md)
documents every field. The parts that most often need a change afterwards:

- `build`: where the build comes from. `github_deploy` reads the latest successful run of a
  deploy workflow; `command` runs a script that prints
  `{"app_version", "deploy_sha", "warnings"}`.
- `commit_env`: environment for party commits, e.g. `{"HUSKY": "0"}`, when a pre-commit hook
  can't run in a worktree.
- `automation.setup_helpers` / `transient_errors`: which spec failures come from third-party
  setup (repair the helper, not the case) or from refusals that judge nothing (rate limits).

## Upgrading an installed repo

`party.py` and `test_party.py` are identical in every repo, and all repo-specific behaviour
is in `test-party.json`. To upgrade, ask Claude to "upgrade party.py from test-party-kit", or
copy the two files from
`skills/installing-test-parties/templates/core/.claude/skills/test-party/` and run
`python3 -m unittest discover -s .claude/skills/test-party`. The installed `SKILL.md` files
are the repo's own to edit; reinstalling with `--force` would overwrite them.

## Develop

```
skills/installing-test-parties/
  SKILL.md                 # the generator skill: survey, interview, install, verify
  install.py               # renders templates from an answers file; --dry-run to preview
  answers.md               # every answer field
  answers.example.json     # a full automation example
  templates/core/          # always installed
  templates/automation/    # the e2e workspace, installed in automation mode
```

Templates use `{{PLACEHOLDER}}` values and `<!-- if:flag -->…<!-- endif:flag -->` blocks
(`automation`, `manual`, `glossary`, `limitations`, `ci_check`). The installer refuses to write
anything if a placeholder is left unrendered.

Tests:

```bash
python3 -m unittest discover -s skills/installing-test-parties -p 'test_install.py'
```

```bash
python3 -m unittest discover -s skills/installing-test-parties/templates/core/.claude/skills/test-party
```

The second suite runs `party.py` against throwaway git repos with stubbed `gh`, `npm` and `npx`,
in both modes. It takes about three minutes.

Extracted and generalised from the Canva Microsoft Teams integration, where Test Parties
started.
