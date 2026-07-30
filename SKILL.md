---
name: task-harness
description: Build and operate an auditable multi-session task harness with dependency-aware tasks, executable verification, evidence-bound completion, controlled amendments, and independent review. Use for large implementations, migrations, project planning, or repairing an existing feature_list.json harness.
argument-hint: "[project name] [requirements or migration target]"
disable-model-invocation: false
user-invocable: true
---

# Task Harness

Create a durable, auditable control plane for work that spans Agent sessions.
The original four-file harness remains recognizable, but `passes` is only a
compatibility projection. A task becomes passed only from current evidence and
an independent review.

Read [references/methodology.md](references/methodology.md) before creating or
migrating a harness. For a concrete merge/split and reuse analysis, read
[references/examples/sub2api-migration.md](references/examples/sub2api-migration.md).

## Workflow

### 1. Establish authorization and repository boundaries

Record the project root, source revision, working-tree state, target branch, and
remote ownership. Treat local edits, dependency installation, commit, push, and
production access as separate actions. This Skill never supplies authorization
for any of them.

### 2. Inventory before decomposition

Search for existing task manifests, plans, issues, CI commands, package scripts,
build tags/features, tests, generated code, and modules that already own the
requested responsibilities. For every proposed task, record whether it will
`reuse`, `extend_via_amendment`, `supersede`, or `create_with_justification`.
Do not create a parallel scheduler, parser, cache, page, service, or policy
engine when an established owner can be extended.

### 3. Draft a dependency graph

Use the v2 template at
[references/templates/feature_list.json](references/templates/feature_list.json).
Each feature must declare:

- stable ID, priority, canonical `status`, and compatibility `passes`
- definition revision and explicit `depends_on`
- scoped targets with path, role, responsibility, and existence expectation
- object-form steps and observable acceptance criteria
- executable verification argv, cwd, timeout, criterion binding, variants, and
  minimum discovered tests
- reuse decision and explicit parallel implementations to forbid
- references to evidence, reviews, and amendments

Prefer one independently verifiable behavior per task. Merge tasks only when
they share one implementation primitive and one verification boundary. Split a
task when schema, behavior mode, UI, enforcement, or rollback can fail
independently.

### 4. Run an independent specification review

Before freezing revision 1, use a different Agent/session to review:

- paths and ownership responsibilities against the actual codebase
- dependency order and cycles
- executable commands, build tags/features, target test names, and nonzero test
  discovery
- hard assertions and numeric performance limits
- overlap with existing implementation and other tasks
- safety boundaries and rollback independence

Close findings before implementation. Record the reviewer identity and decision
in `progress.txt`. A reviewer cannot approve their own specification or task
evidence.

### 5. Generate the harness

Keep these compatibility entry points in the project root:

```text
feature_list.json
progress.txt
init.sh
task.json
AGENTS.md
```

Create deterministic controls under `.task-harness/`:

```text
.task-harness/
  amendments/
  evidence/<task-id>/
  reviews/<task-id>/
  snapshots/
  scripts/validate_harness.py
```

Copy the validator from [scripts/validate_harness.py](scripts/validate_harness.py)
and the templates from [references/templates/](references/templates/). Adapt
commands and paths to the project; do not weaken the evidence fields.

### 6. Validate before implementation

Run:

```sh
python .task-harness/scripts/validate_harness.py --root . --strict-paths
bash init.sh
```

The manifest is blocked when a prerequisite, required path, dependency,
verification command, build variant, acceptance mapping, or independent audit
is unresolved. An exit code of zero is insufficient for test checks: the
recorded discovered test count must meet the declared minimum.

### 7. Execute one eligible task

Select the smallest-priority `ready` task whose dependencies are `passed`.
Move it to `in_progress`, implement only its scope, and extend the existing
owners recorded in `reuse`. If the definition is wrong, stop and use an
amendment; do not silently edit it.

### 8. Record immutable verification evidence

Write one evidence record per attempt using
[references/templates/.harness/evidence.json](references/templates/.harness/evidence.json).
Evidence must bind the task definition revision and source revision and record
exact argv, cwd, environment variant/build tags/features, timeout, exit code,
test discovery counts, output digests/excerpts, and performance results.

Rules:

- test checks require at least one discovered test unless an approved explicit
  non-test check applies
- include all declared build tags, language features, configurations, and
  platforms
- concurrency changes require race/thread checks where supported
- parser boundaries require bounded fuzz/property checks
- hot paths require numeric benchmark limits, not subjective language
- a changed definition or affected source revision makes old evidence stale

After complete evidence, use `awaiting_review`; do not set `passed` directly.

### 9. Require independent completion review

A different actor/session reviews the exact evidence ID, changed scope,
acceptance coverage, discovered tests, variants, performance limits, and reuse
constraints. Store the result with
[references/templates/.harness/review.json](references/templates/.harness/review.json).
Only an approved current review allows `status: passed` and `passes: true`.
Rejected review returns the task to work with a new attempt and review.

### 10. Amend definitions without rewriting history

Use [references/templates/.harness/amendment.json](references/templates/.harness/amendment.json).
An amendment records base manifest/definition revisions, structured patch,
reason, impact, proposer, independent approver, and applied revisions. Apply it
only if the base revision still matches. Increment both revisions as applicable;
mark old evidence stale. A passed task affected by the amendment becomes
`regressed`, not silently green.

Keep superseded tasks and their history. Never delete a task to hide a merge,
split, correction, or regression.

## Canonical states

```text
proposed -> ready -> in_progress -> awaiting_review -> passed
                         |               |
                         v               v
                      blocked      review_rejected
                         |
                         v
                verification_failed

passed -> regressed -> in_progress | blocked | awaiting_review
any nonterminal -> superseded | cancelled
```

`passes` must always equal `(status == "passed")`.

## Per-session order

1. Run `bash init.sh`; read `progress.txt` and the manifest.
2. Verify repository, toolchain, dependency, and authorization boundaries.
3. Select one dependency-eligible task.
4. Implement only its scope and reuse existing modules.
5. Run every declared check and create evidence.
6. Obtain independent review of that evidence.
7. Derive status and compatibility `passes` together.
8. Append the session log.
9. Commit or push only when currently authorized and after verifying the target.

## Strict rules

- Task definitions change only through approved, revisioned amendments.
- No task passes without current evidence and independent approval.
- Zero discovered tests fail a test check.
- Build tags/features/configurations are part of verification, not optional notes.
- Blockers are structured state, not prose that can be ignored.
- Regressions invalidate green status.
- `progress.txt` explains history but never overrides machine state.
- `task.json` contains project policy; milestone status is derived from tasks.
- Do not force install, commit, push, or production actions.
