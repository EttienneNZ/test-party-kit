# Answers file

`install.py <repo> <answers.json>` reads one JSON object. `answers.example.json` is a full
automation example; drop `automation` (or set it to `null`) for manual mode.

## Required

| Field | Example | Used for |
| --- | --- | --- |
| `product` | `"Acme Portal"` | Skill descriptions and prose |
| `environment` | `"staging"` | Where cases run, as a name |
| `issue_tracker` | `"Jira project ACME, through the Atlassian MCP tools"` | Fetching stories and drafting bugs. It completes both "fetch it from …" and "a draft bug ticket for …", so write a noun phrase |
| `baseline` | `"the tester is signed in to … as a member, with default settings"` | The state every case starts from |

## Optional

| Field | Default | Notes |
| --- | --- | --- |
| `remote` | `"origin"` | |
| `base_branch` | `"main"` | Cases are read from `<remote>/<base_branch>` |
| `plans_dir` | `"docs/test-plans"` | One CSV per feature |
| `parties_dir` | `"docs/test-parties"` | Results, one folder per party |
| `party_branch_prefix` | `"test-party/"` | |
| `bug_conventions` | `null` | Path to the team's ticket-writing rules |
| `glossary` | `null` | Path; write-test-plan names things as it does |
| `limitations` | `null` | Path; untestable platform constraints |
| `session_cases` | `5` | Cases an agent runs per session |
| `commit_env` | `{}` | Env for party commits, e.g. `{"HUSKY": "0"}` |
| `build` | `{}` | `{"github_deploy": {"workflow": "deploy.yml", "title_contains": "(staging)", "branch": "main"}}` and/or `{"command": ["./scripts/build-info"]}`, which prints `{"app_version", "deploy_sha", "warnings"}` |
| `build_note` | `""` | Spliced into a sentence as ` (…)`: a lowercase clause, no full stop |
| `ci_check` | `false` | `true` when you will add a CI step running `party.py check`; the skills then say CI enforces it |
| `environment_url` | `null` | Becomes the first tip |
| `tips` | `[]` | Markdown strings, one per tip, without the leading `- `: URLs, quirks |
| `automation` | `null` | See below |

## `automation`

| Field | Default | Notes |
| --- | --- | --- |
| `personas` | — (required) | List; see below |
| `e2e_dir` | `"e2e"` | |
| `setup_helpers` | `null` | Filename regex under `e2e/src` for helpers that drive a third-party system in setup. Failures there are `setup`, not `product` |
| `setup_label` | `"setup"` | That system's name, e.g. `"Stripe"` |
| `transient_errors` | `[]` | Error regexes for refusals that judge nothing (rate limits) |
| `transient_label` | `"a transient refusal"` | e.g. `"a rate limit"` |
| `blocked` | `[]` | `[{"needs": "a user in another org", "note": "needs an outsider persona"}]` |
| `playwright_mcp_version` | `"0.0.83"` | Pin for `@playwright/mcp` |

Each persona: `name`, `holds` (what its browser is signed in to, for the skill's table),
`port` (unique, e.g. 9301+), `signInUrls`, `homeUrl` (the tab specs act in), `signedOutUrl`
(a regex matching its sign-in page URL), and optionally `account` (facts like email and org)
and `fixtures` (named data that must exist in the account).
