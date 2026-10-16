"""Tests for install.py, run against throwaway repos.

Run: python3 -m unittest discover -s skills/installing-test-parties -p 'test_install.py'
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
INSTALL = HERE / 'install.py'
EXAMPLE = json.loads((HERE / 'answers.example.json').read_text())
PLAN = 'Sharing\nID,Scenario,Action,Steps,Expected Result\nSH-001,Share,Open share,1. Click Share,1. Dialog opens\n'
ENV = {'GIT_AUTHOR_NAME': 'T', 'GIT_AUTHOR_EMAIL': 't@example.com',
       'GIT_COMMITTER_NAME': 'T', 'GIT_COMMITTER_EMAIL': 't@example.com'}


def git(*args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**__import__('os').environ, **ENV}).stdout


class Install(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        git('init', '--quiet', '--bare', '--initial-branch=main', 'origin.git', cwd=self.root)
        git('clone', '--quiet', 'origin.git', 'repo', cwd=self.root)
        self.repo = self.root / 'repo'

    def install(self, answers, *extra):
        path = self.root / 'answers.json'
        path.write_text(json.dumps(answers))
        return subprocess.run([sys.executable, str(INSTALL), str(self.repo), str(path), *extra],
                              capture_output=True, text=True)

    def manual(self, **overrides):
        return {**EXAMPLE, 'automation': None, **overrides}

    def read(self, rel):
        return (self.repo / rel).read_text()

    def test_manual_install_writes_both_skills_without_automation(self):
        done = self.install(self.manual())

        self.assertEqual(done.returncode, 0, done.stderr)
        skill = self.read('.claude/skills/test-party/SKILL.md')
        self.assertIn('--method human', skill)
        self.assertNotIn('keep-spec', skill)
        self.assertNotIn('<!--', skill)
        self.assertIn('## 3. Pick the work', skill)
        self.assertIn('fetch it from Jira project ACME', self.read('.claude/skills/write-test-plan/SKILL.md'))
        self.assertIsNone(json.loads(self.read('.claude/skills/test-party/test-party.json'))['automation'])
        self.assertFalse((self.repo / 'e2e').exists())
        self.assertIn('.claude/skills/test-party/tips.local.md', self.read('.gitignore'))

    def test_automation_install_adds_the_e2e_scaffold_and_persona_example(self):
        done = self.install(EXAMPLE)

        self.assertEqual(done.returncode, 0, done.stderr)
        skill = self.read('.claude/skills/test-party/SKILL.md')
        self.assertIn('keep-spec', skill)
        self.assertNotIn('--method human', skill)
        self.assertIn('| `member` | a regular member of the QA org, signed in to the portal |', skill)
        self.assertIn('helper it names as `helper`', skill)
        self.assertIn('Stripe', skill)
        config = json.loads(self.read('.claude/skills/test-party/test-party.json'))
        self.assertEqual(config['automation']['preflight'], ['npm', '--prefix', 'e2e', 'run', '--silent', 'preflight'])
        self.assertIn('"homeUrl": "https://staging.acme.test/"', self.read('e2e/personas.example.ts'))
        self.assertIn('"name": "repo-e2e"', self.read('e2e/package.json'))

    def test_installed_party_py_reads_the_plans_on_the_configured_base(self):
        self.install(self.manual(plans_dir='qa/plans', parties_dir='qa/parties'))
        (self.repo / 'qa/plans/sharing.csv').write_text(PLAN)
        git('add', '-A', cwd=self.repo)
        git('commit', '--quiet', '-m', 'install', cwd=self.repo)
        git('push', '--quiet', 'origin', 'HEAD:main', cwd=self.repo)

        shown = subprocess.run([sys.executable, '.claude/skills/test-party/party.py', 'show', 'SH-001'],
                               cwd=self.repo, capture_output=True, text=True)

        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn('SH-001 · Sharing · Share', shown.stdout)
        self.assertIn('](../../../qa/parties/README.md)', self.read('.claude/skills/test-party/SKILL.md'))
        self.assertIn('[`qa/plans/`](../plans)', self.read('qa/parties/README.md'))

    def test_refuses_to_overwrite_without_force(self):
        self.install(self.manual())
        (self.repo / '.claude/skills/test-party/SKILL.md').write_text('local edits\n')

        done = self.install(self.manual())

        self.assertNotEqual(done.returncode, 0)
        self.assertIn('rerun with --force', done.stderr)
        self.assertEqual(self.read('.claude/skills/test-party/SKILL.md'), 'local edits\n')
        self.assertEqual(self.install(self.manual(), '--force').returncode, 0)

    def test_missing_required_answers_write_nothing(self):
        answers = self.manual()
        del answers['baseline']

        done = self.install(answers)

        self.assertNotEqual(done.returncode, 0)
        self.assertIn('missing baseline', done.stderr)
        self.assertFalse((self.repo / '.claude').exists())

    def test_refuses_a_directory_that_is_not_a_repo_root(self):
        (self.repo / 'sub').mkdir()
        path = self.root / 'answers.json'
        path.write_text(json.dumps(self.manual()))

        done = subprocess.run([sys.executable, str(INSTALL), str(self.repo / 'sub'), str(path)],
                              capture_output=True, text=True)

        self.assertNotEqual(done.returncode, 0)
        self.assertIn('not the root of a git repo', done.stderr)

    def test_optional_sections_drop_out_when_unanswered(self):
        self.install(self.manual(glossary=None, limitations=None, ci_check=False, bug_conventions=None))

        plan_skill = self.read('.claude/skills/write-test-plan/SKILL.md')
        self.assertNotIn('glossary', plan_skill.lower())
        self.assertNotIn('CI runs the same check', plan_skill)
        self.assertNotIn(', following', self.read('.claude/skills/test-party/SKILL.md'))


    def test_dry_run_names_existing_files_and_gitignore_lines_and_writes_nothing(self):
        (self.repo / 'docs/test-parties').mkdir(parents=True)
        (self.repo / 'docs/test-parties/README.md').write_text('ours\n')

        done = self.install(self.manual(), '--dry-run')

        self.assertEqual(done.returncode, 0, done.stderr)
        plan = json.loads(done.stdout)
        self.assertEqual(plan['already_exist'], ['docs/test-parties/README.md'])
        self.assertIn('.claude/skills/test-party/tips.local.md', plan['gitignore_appends'])
        self.assertFalse((self.repo / '.claude').exists())

    def test_tips_get_one_bullet_each_after_the_environment_url(self):
        self.install(self.manual(environment_url='https://staging.acme.test', tips=['- Admin needs VPN', 'Clear cache']))

        skill = self.read('.claude/skills/test-party/SKILL.md')
        self.assertIn('## Tips\n\n- **Staging:** https://staging.acme.test\n- Admin needs VPN\n- Clear cache\n', skill)
        self.assertFalse(__import__('os').access(self.repo / '.claude/skills/test-party/test_party.py', __import__('os').X_OK))


if __name__ == '__main__':
    unittest.main()
