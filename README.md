# Task Harness

An auditable long-running Agent Skill derived from the original
`kangarooking/task-harness` workflow.

Version 2 keeps the familiar root files while fixing the failure modes exposed
by real repository audits:

- revisioned, independently approved task amendments
- dependency-aware canonical task states with legacy `passes` projection
- executable verification and nonzero test discovery
- build tag/feature/platform matrices
- evidence-bound completion and independent second review
- structured blockers and regressions
- target responsibilities and reuse constraints to prevent parallel systems
- explicit authorization boundaries for install, commit, push, and production

## What changed in v2

The v2 redesign was driven by a real Sub2API audit where inaccurate paths,
missing Go build tags, zero-test false positives, and an immutable task list made
safe continuation impossible. The new harness adds:

- canonical states such as `ready`, `blocked`, `awaiting_review`, `passed`, and
  `regressed`, with `passes` retained only as a compatibility projection
- dependency gates, stable ownership targets, reuse fingerprints, and explicit
  prohibitions against creating parallel schedulers, parsers, caches, services,
  pages, or policy engines
- argv-form verification plans bound to cwd, timeout, acceptance criteria,
  required build-tag/feature/platform variants, and minimum discovered tests
- immutable evidence records bound to source/workspace fingerprints, exact
  verification plans, test counts, output digests, and execution identity
- independent completion review that binds the exact evidence ID and rejects
  stale revisions, unresolved findings, or reused actor/session identities
- independently approved amendments with a global manifest revision chain,
  task definition revisions, protected state fields, structured patches, and
  canonical definition digests
- strict path containment for targets, evidence, reviews, amendments, and check
  working directories
- explicit separation between local edits, dependency installation, commit,
  push, and production authorization

The validator includes adversarial regressions for forged check kinds or
commands, zero and boolean test counts, incomplete variant matrices, stale source
revisions, path traversal, unpassed dependencies, unrelated amendment patches,
missing review metadata, and manifest revision jumps without amendments.

The implementation was closed through two independent adversarial review rounds.
The first review exposed plan/evidence substitution, incomplete variant coverage,
path escape, stale source acceptance, declarative-only reviews, and unvalidated
amendments. The second review found patch/result drift, unpassed dependencies,
self-reported source fingerprints, boolean test-count coercion, timeout drift,
and missing review metadata. Each reproduced bypass now has a negative regression
test. The current suite contains 24 tests, the unrendered template passes strict
validation with zero warnings, and the validator, shell initializer, and JSON
templates are syntax checked.

## Migration workflow

For an existing legacy harness, do not edit a wrong immutable definition in
place and then preserve a misleading green state. Use this sequence:

1. Freeze the legacy manifest and record its source/workspace fingerprint.
2. Audit actual code owners, paths, build tags, test names, toolchain versions,
   dependencies, and authorization boundaries.
3. Draft a v2 dependency graph. Merge only tasks sharing one implementation and
   verification boundary; split schema, enforcement, UI, performance, and
   rollout when they can fail or roll back independently.
4. Run an independent specification review and close all findings.
5. Install the v2 validator and control directories, then validate with
   `--strict-paths` before implementation.
6. Keep legacy completion values false unless current evidence proves them.
   Future definition changes use approved amendments and invalidate stale
   evidence.

The Sub2API migration informed the recommended ordering: harness and toolchain,
early fixtures and taxonomy, compatibility-first configuration, formula and UI,
a shared preflight, capability-aware scheduling, rolling health and tuple-level
circuits, retry/latency/queue governance, then full regression and rollout.

## Task design guidance

Before freezing a manifest, inventory the existing code owners and tests. Merge
tasks only when they share one implementation primitive and one verification
boundary. Split schema, enforcement, UI, rollout, and performance work when each
can fail or roll back independently. Establish fixtures, toolchain checks,
configuration defaults, and shared taxonomies before behavior that depends on
them; schedule full regression and rollout documentation after the behavior is
implemented.

The Sub2API case study demonstrates the concrete decisions used in this release:
combine generic request preflight with deterministic payload rules, combine
rolling-health collection with shadow penalties, keep enforce-mode circuit
breaking separate, split early test infrastructure from final regression, and
split configuration defaults from UI and dangerous-combination validation.

## Layout

- `SKILL.md`: Agent workflow and strict rules
- `references/methodology.md`: design rationale and migration guidance
- `references/templates/`: v2 manifest, evidence, review, amendment, task, log,
  and initializer templates
- `references/examples/sub2api-migration.md`: real read-only migration case study
- `scripts/validate_harness.py`: dependency, path, criteria, evidence, review,
  and zero-test validator
- `tests/test_validate_harness.py`: validator regression tests

## Validate

```sh
python -m unittest discover -s tests -v
python scripts/validate_harness.py --root references/templates
```

Template targets are non-required placeholders so the unrendered template is
self-validating. A generated project must replace them with real paths, set
`required: true`, and validate with `--strict-paths`.

## License

MIT-0, matching the referenced original Skill.
