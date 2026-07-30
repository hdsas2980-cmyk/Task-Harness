# Sub2API migration case study

This case study records the reusable conclusions from a read-only audit of a real
20-task Go/Vue harness. It is not a production runbook and grants no permission
to access, deploy, restart, or modify any remote system.

## Why migration was blocked

The legacy manifest contained inaccurate paths and verification commands, while
its rules prohibited every definition change except `passes: false -> true`.
Some Go tests used a `unit` build tag but their commands omitted `-tags=unit`, so
a successful command could execute zero target tests. The module also required a
newer Go toolchain than the local environment. All legacy pass values therefore
remained false.

## Revised dependency order

1. Harness revision, source/toolchain prerequisites, and deterministic dependency restore.
2. Sanitized fixtures, test-discovery gates, benchmarks, and the shared error/attempt taxonomy.
3. Minimal `off -> shadow -> enforce` configuration with compatibility defaults.
4. Health formula characterization, heartbeat correction, backend breakdown contract, then UI.
5. A single request preflight framework combining generic parsing and deterministic structure rules.
6. Three-state capability schema, request requirements, scheduler shadow filtering, then admin UI.
7. Retry/attempt controller and stage latency, followed by first-output failover integration.
8. Rolling health plus shadow penalty, then tuple-level enforce/circuit recovery.
9. Capacity observability, bounded/fair queueing, complete regression, and rollout documentation.

## Merge and split decisions

- Merge generic request parsing and deterministic payload checks because they
  share one bounded body scan and one shadow/enforce contract.
- Merge rolling-health collection with shadow penalty calculation; keep enforce
  circuit breaking and graduated recovery as a separate task.
- Split configuration into early compatibility defaults, effective-value UI,
  and late dangerous-combination validation.
- Split test infrastructure into an early fixtures/discovery/baseline task and a
  late full race/fuzz/benchmark regression task.
- Split latency instrumentation from capacity percentile APIs and queue policy.

Keep formula and heartbeat changes separate, backend contracts separate from UI,
and retry policy separate from first-output timeout behavior.

## Reuse map

The migration must point each task at the established owner and explicitly ban a
parallel implementation:

- Extend the existing health score/dashboard calculation, not a second score service.
- Extend the existing operations error logger and repository aggregations, not a second classifier.
- Share the existing OpenAI-compatible request parsing layer, not a second JSON parser.
- Extend the existing account scheduler, not a parallel candidate selector.
- Extend the existing account/model transient and runtime-block state, not a new health cache.
- Integrate with the existing first-output staging/failover guard, not another timeout loop.
- Use the actual account view and edit components, not a nonexistent replacement page.
- Add modes to the existing gateway configuration, not a separate configuration center.

## Verification gates illustrated by the audit

- Compare the installed toolchain with the module declaration; mismatch means `blocked`.
- Include required Go build tags and require explicit test names plus a discovered count above zero.
- Run precise target tests, affected package suites, race tests for concurrent state,
  bounded fuzzing for parsers, and numeric benchmark thresholds for hot paths.
- Bind every pass to manifest/definition revision, source revision, exact argv/cwd,
  exit code, test counts, variants, assertions, and performance results.
- Require an independent review of the exact evidence ID before deriving `passed`.
- Assert invariants such as shadow response equivalence, unknown capability retention,
  zero active groups without candidates, retry/time budgets, cancellation cleanup,
  and no replay after response commitment.
