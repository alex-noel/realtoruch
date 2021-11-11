import type { FullConfig, FullResult, Reporter, Suite } from '@playwright/test/reporter';
import { writeFileSync } from 'node:fs';

export default class AggregateReporter implements Reporter {
  private suite?: Suite;
  onBegin(_config: FullConfig, suite: Suite) { this.suite = suite; }
  onEnd(result: FullResult) {
    const counts = { passed: 0, failed: 0, skipped: 0 };
    for (const test of this.suite?.allTests() || []) {
      const outcome = test.outcome();
      if (outcome === 'expected') counts.passed++;
      else if (outcome === 'skipped') counts.skipped++;
      else counts.failed++;
    }
    if (process.env.E2E_SUMMARY_FILE)
      writeFileSync(process.env.E2E_SUMMARY_FILE, JSON.stringify({ status: result.status, counts }) + '\n');
  }
}
