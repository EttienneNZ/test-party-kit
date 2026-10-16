import { spawnSync } from 'node:child_process';
import { relative, resolve } from 'node:path';
import { E2E_DIR } from './personas.ts';

interface Annotation {
  type: string;
  description?: string;
}
interface ListedTest {
  annotations: Annotation[];
}
interface ListedSpec {
  title: string;
  file: string;
  tests: ListedTest[];
}
interface ListedSuite {
  specs?: ListedSpec[];
  suites?: ListedSuite[];
}

function* specsIn(suite: ListedSuite): Generator<ListedSpec> {
  yield* suite.specs ?? [];
  for (const child of suite.suites ?? []) yield* specsIn(child);
}

// Playwright exits 1 when there are no specs yet, with a valid report that lists none.
const listing = spawnSync('npx', ['playwright', 'test', '--list', '--reporter=json'], {
  cwd: E2E_DIR,
  encoding: 'utf8',
});
const report: { config: { rootDir: string }; suites: ListedSuite[] } = JSON.parse(listing.stdout);

const cases = report.suites
  .flatMap((suite) => [...specsIn(suite)])
  .map((spec) => {
    const annotations = spec.tests.flatMap((t) => t.annotations);
    const value = (type: string) => annotations.find((a) => a.type === type)?.description;
    return {
      case_id: value('case_id'),
      case_hash: value('case_hash'),
      file: relative(E2E_DIR, resolve(report.config.rootDir, spec.file)),
      title: spec.title,
    };
  })
  .filter((c) => c.case_id);

console.log(JSON.stringify(cases, null, 2));
