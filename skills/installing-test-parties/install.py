#!/usr/bin/env python3
"""Installs write-test-plan, test-party and party.py into a git repo, from an answers file. See SKILL.md."""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / 'templates'
SKILL_DIR = '.claude/skills/test-party'
VERBATIM = {'party.py', 'test_party.py'}
REQUIRED = ['product', 'environment', 'issue_tracker', 'baseline']
DEFAULTS = {
    'remote': 'origin',
    'base_branch': 'main',
    'plans_dir': 'docs/test-plans',
    'parties_dir': 'docs/test-parties',
    'party_branch_prefix': 'test-party/',
    'bug_conventions': None,
    'glossary': None,
    'limitations': None,
    'session_cases': 5,
    'commit_env': {},
    'build': {},
    'build_note': '',
    'ci_check': False,
    'tips': [],
    'environment_url': None,
    'automation': None,
}
AUTOMATION_DEFAULTS = {
    'e2e_dir': 'e2e',
    'setup_helpers': None,
    'setup_label': 'setup',
    'transient_errors': [],
    'transient_label': 'a transient refusal',
    'playwright_mcp_version': '0.0.83',
    'blocked': [],
}
BLOCK = re.compile(r'^<!-- if:(\w+) -->\n(.*?)^<!-- endif:\1 -->\n', re.M | re.S)
PLACEHOLDER = re.compile(r'\{\{(\w+)\}\}')


class InstallError(Exception):
    pass


def load_answers(path):
    answers = {**DEFAULTS, **json.loads(Path(path).read_text())}
    missing = [k for k in REQUIRED if not answers.get(k)]
    if missing:
        raise InstallError(f'answers file is missing {", ".join(missing)}')
    if answers['automation'] is not None:
        answers['automation'] = {**AUTOMATION_DEFAULTS, **answers['automation']}
        personas = answers['automation'].get('personas') or []
        if not personas:
            raise InstallError('automation needs at least one persona')
        for persona in personas:
            absent = [k for k in ('name', 'holds', 'port', 'signInUrls', 'homeUrl', 'signedOutUrl') if k not in persona]
            if absent:
                raise InstallError(f'persona {persona.get("name", "?")} is missing {", ".join(absent)}')
    return answers


def party_config(answers):
    """test-party.json: what party.py needs, and nothing the skills only describe."""
    config = {k: answers[k] for k in ('remote', 'base_branch', 'plans_dir', 'parties_dir', 'party_branch_prefix',
                                      'commit_env', 'build')}
    auto = answers['automation']
    if auto:
        e2e = auto['e2e_dir']
        config['automation'] = {
            'e2e_dir': e2e,
            'specs_dir': f'{e2e}/specs',
            'helpers_dir': f'{e2e}/src',
            'shared_paths': [f'{e2e}/node_modules', f'{e2e}/personas.local.ts'],
            'typecheck': ['npm', '--prefix', e2e, 'run', '--silent', 'typecheck'],
            'preflight': ['npm', '--prefix', e2e, 'run', '--silent', 'preflight'],
            'setup_helpers': auto['setup_helpers'],
            'setup_label': auto['setup_label'],
            'transient_errors': auto['transient_errors'],
            'transient_label': auto['transient_label'],
        }
    else:
        config['automation'] = None
    return config


def link(target, from_dir):
    return os.path.relpath(target, from_dir)


def table(header, rows):
    lines = ['| ' + ' | '.join(header) + ' |', '|' + ' --- |' * len(header)]
    return '\n'.join(lines + ['| ' + ' | '.join(row) + ' |' for row in rows])


def values(answers, repo_name):
    auto = answers['automation']
    parties, plans = answers['parties_dir'], answers['plans_dir']
    e2e = auto['e2e_dir'] if auto else 'e2e'
    steps = (7, 8, 10) if auto else (3, 4, 5)
    tips = ([f'**{answers["environment"].capitalize()}:** {answers["environment_url"]}']
            if answers['environment_url'] else []) + [tip.removeprefix('- ') for tip in answers['tips']]
    tips = [f'- {tip}' for tip in tips] or ['- Add tips for this product here as testers find them.']
    v = {
        'PRODUCT': answers['product'],
        'ENVIRONMENT': answers['environment'],
        'REMOTE': answers['remote'],
        'BASE_BRANCH': answers['base_branch'],
        'PLANS_DIR': plans,
        'PARTIES_DIR': parties,
        'PARTY_BRANCH_PREFIX': answers['party_branch_prefix'],
        'SPEC_BRANCH_PREFIX': 'test/case-specs/',
        'ISSUE_TRACKER': answers['issue_tracker'],
        'BUG_CONVENTIONS': f', following `{answers["bug_conventions"]}`' if answers['bug_conventions'] else '',
        'GLOSSARY': answers['glossary'] or '',
        'LIMITATIONS': answers['limitations'] or '',
        'SESSION_CASES': str(answers['session_cases']),
        'BASELINE': answers['baseline'],
        'SESSION_CONSTRAINT': 'Token cost is the constraint' if auto else "The tester's time and focus are the constraint",
        'BUILD_NOTE': f' ({answers["build_note"]})' if answers['build_note'] else '',
        'TIPS': '\n'.join(tips),
        'STEP_PICK': str(steps[0]),
        'STEP_RUN': str(steps[1]),
        'STEP_REPORT': str(steps[2]),
        'PARTIES_README_LINK': link(f'{parties}/README.md', SKILL_DIR),
        'PLANS_LINK': link(plans, parties),
        'PARTY_PY_LINK': link(f'{SKILL_DIR}/party.py', parties),
        'E2E_DIR': e2e,
        'SPECS_DIR': f'{e2e}/specs',
        'HELPERS_DIR': f'{e2e}/src',
        'SPECS_LINK': link(f'{e2e}/specs', parties),
        'E2E_README_LINK': link(f'{e2e}/README.md', SKILL_DIR),
        'PARTIES_README_FROM_E2E': link(f'{parties}/README.md', e2e),
        'E2E_PACKAGE': f'{repo_name}-e2e',
        'AUTOMATED_COUNT': ' · <a> automated' if auto else '',
        'AUTOMATION_README_MENTION': '',
    }
    if auto:
        personas = auto['personas']
        v.update({
            'AUTOMATION_README_MENTION': f', Automated Case and Case Spec — and [`{e2e}/README.md`]'
                                         f'({v["E2E_README_LINK"]}) for the persona browsers and preflight',
            'SETUP_LABEL': auto['setup_label'],
            'TRANSIENT_LABEL': auto['transient_label'],
            'SETUP_HELPERS_NOTE': f' (`{auto["setup_helpers"]}`)' if auto['setup_helpers'] else ' (none yet)',
            'FIRST_PERSONA': personas[0]['name'],
            'PLAYWRIGHT_MCP_VERSION': auto['playwright_mcp_version'],
            'PERSONAS_TABLE': table(['Persona', 'Browser holds'],
                                    [[f'`{p["name"]}`', p['holds']] for p in personas]),
            'BLOCKED_TABLE': table(['Case needs', 'Note'],
                                   [[b['needs'], f'`{b["note"]}`'] for b in auto['blocked']]
                                   or [['an account fact no persona holds', '`needs <the account fact>`']]),
        })
    return v


def flags(answers):
    return {'automation': bool(answers['automation']), 'manual': not answers['automation'],
            'glossary': bool(answers['glossary']), 'limitations': bool(answers['limitations']),
            'ci_check': bool(answers['ci_check'])}


def render(text, v, on):
    text = BLOCK.sub(lambda m: m.group(2) if on.get(m.group(1)) else '', text)
    text = PLACEHOLDER.sub(lambda m: v[m.group(1)] if m.group(1) in v else m.group(0), text)
    return re.sub(r'\n{3,}', '\n\n', text)


def personas_example(answers):
    personas = {}
    for p in answers['automation']['personas']:
        personas[p['name']] = {
            'port': p['port'],
            'userDataDir': f'.browsers/{p["name"]}',
            'signInUrls': p['signInUrls'],
            'homeUrl': p['homeUrl'],
            'signedOutUrl': p['signedOutUrl'],
            **({'account': p['account']} if p.get('account') else {}),
            **({'fixtures': p['fixtures']} if p.get('fixtures') else {}),
        }
    body = json.dumps({'tester': 'your-name', 'personas': personas}, indent=2)
    return ('// Copy to personas.local.ts (gitignored) and fill in your own accounts. Specs and the launcher read only\n'
            '// the local file, so no spec hardcodes a tester\'s accounts. Fields are documented in src/personas.ts.\n'
            "import type { PersonaFile } from './src/personas.ts';\n\n"
            f'export default {body} satisfies PersonaFile;\n')


def planned_files(answers):
    """(source or None, destination relative to the repo, how to write it)"""
    files = []
    for source in sorted((TEMPLATES / 'core').rglob('*')):
        if source.is_file():
            rel = source.relative_to(TEMPLATES / 'core').as_posix()
            rel = rel.replace('docs/test-parties/', f'{answers["parties_dir"]}/', 1)
            rel = rel.replace('docs/test-plans/', f'{answers["plans_dir"]}/', 1)
            files.append((source, rel, 'verbatim' if source.name in VERBATIM else 'render'))
    files.append((None, f'{SKILL_DIR}/test-party.json', 'config'))
    auto = answers['automation']
    if auto:
        for source in sorted((TEMPLATES / 'automation/e2e').rglob('*')):
            if source.is_file():
                rel = f'{auto["e2e_dir"]}/{source.relative_to(TEMPLATES / "automation/e2e").as_posix()}'
                files.append((source, rel, 'render'))
        files.append((None, f'{auto["e2e_dir"]}/personas.example.ts', 'personas'))
    return files


def append_gitignore(target, lines):
    path = target / '.gitignore'
    existing = path.read_text().splitlines() if path.exists() else []
    missing = [line for line in lines if line not in existing]
    if missing:
        prefix = '' if not existing or path.read_text().endswith('\n') else '\n'
        with path.open('a') as f:
            f.write(prefix + '\n'.join(['# Test Party', *missing]) + '\n')
    return missing


def repo_root(target):
    target = Path(target).resolve()
    top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=target, capture_output=True, text=True)
    if top.returncode or Path(top.stdout.strip()).resolve() != target:
        raise InstallError(f'{target} is not the root of a git repo')
    return target


def gitignore_lines(answers):
    return [f'{SKILL_DIR}/tips.local.md'] + (['.playwright-mcp/'] if answers['automation'] else [])


def dry_run(target, answers):
    target = repo_root(target)
    files = [rel for _, rel, _ in planned_files(answers)]
    return {'would_write': files, 'already_exist': [rel for rel in files if (target / rel).exists()],
            'gitignore_appends': gitignore_lines(answers)}


def install(target, answers, force=False):
    target = repo_root(target)
    files = planned_files(answers)
    clashes = [rel for _, rel, _ in files if (target / rel).exists()]
    if clashes and not force:
        raise InstallError('these already exist; rerun with --force to overwrite them:\n  ' + '\n  '.join(clashes))
    v, on = values(answers, target.name), flags(answers)
    contents = {}
    for source, rel, how in files:
        if how == 'verbatim':
            contents[rel] = source.read_bytes()
        elif how == 'config':
            contents[rel] = json.dumps(party_config(answers), indent=2) + '\n'
        elif how == 'personas':
            contents[rel] = personas_example(answers)
        else:
            contents[rel] = render(source.read_text(), v, on)
    leftover = [rel for _, rel, how in files if how == 'render'
                and (PLACEHOLDER.search(contents[rel]) or '<!-- if:' in contents[rel])]
    if leftover:
        raise InstallError(f'unrendered placeholders in {", ".join(leftover)}; nothing was written')
    for rel, content in contents.items():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            dest.write_bytes(content)
            dest.chmod(0o755 if Path(rel).name == 'party.py' else 0o644)
        else:
            dest.write_text(content)
    written = list(contents)
    ignored = append_gitignore(target, gitignore_lines(answers))
    return written, ignored


def verify(target):
    party = [sys.executable, f'{SKILL_DIR}/party.py']
    for command in (['config'], ['check']):
        done = subprocess.run(party + command, cwd=target, capture_output=True, text=True)
        if done.returncode:
            raise InstallError(f'party.py {command[0]} failed after install: {done.stderr.strip()}')
    return done.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', help='root of the git repo to install into')
    parser.add_argument('answers', help='answers JSON; see answers.example.json')
    parser.add_argument('--force', action='store_true', help='overwrite files that already exist')
    parser.add_argument('--dry-run', action='store_true',
                        help='list the files it would write and which already exist, and stop')
    args = parser.parse_args()
    try:
        answers = load_answers(args.answers)
        if args.dry_run:
            print(json.dumps(dry_run(args.target, answers), indent=2))
            return
        written, ignored = install(args.target, answers, args.force)
        checked = verify(Path(args.target).resolve())
    except (InstallError, json.JSONDecodeError) as error:
        sys.exit(f'error: {error}')
    print(json.dumps({'written': written, 'gitignore_added': ignored, 'check': checked}, indent=2))


if __name__ == '__main__':
    main()
