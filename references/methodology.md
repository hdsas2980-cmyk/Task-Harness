# Task Harness methodology

## Purpose

Agents lose conversational context between sessions. A harness externalizes the
work graph, decisions, evidence, and review state so a new session can resume
without guessing. The original `feature_list.json + progress.txt + init.sh`
pattern is useful, but a boolean alone cannot distinguish a verified result from
a mistaken edit.

## Truth model

`feature_list.json` is the canonical task graph. `status` is canonical and
`passes` is retained only for legacy readers:

```text
passes == (status == "passed")
```

Large command outputs and reviews are append-only records below
`.task-harness/`; the manifest stores references. `progress.txt` is narrative
context and cannot override state or evidence.

## Why definitions are revisioned

JSON discourages casual rewriting but cannot prevent it. Permanently freezing a
wrong path or test command creates a deadlock. Task definitions therefore use
optimistic, approved amendments:

1. reference the current manifest and definition revisions
2. explain the correction and impact
3. receive approval from a different actor/session
4. apply a structured patch and increment revisions
5. invalidate stale evidence and regress affected passed tasks

History is retained through amendments and supersession; it is never rewritten.

## Why completion is derived

A successful process exit may run no tests, omit build variants, or validate the
wrong package. Completion requires an immutable evidence record containing the
exact command, working directory, source and definition revisions, exit code,
timeout, discovered test count, variants, and output digest. A separate reviewer
then approves that exact evidence ID.

This creates three distinct responsibilities:

- implementation changes behavior
- verification produces reproducible evidence
- review checks that the evidence proves the declared acceptance criteria

## Task design

A task should have one rollback and verification boundary. Merge work only when
it shares one primitive and cannot be verified meaningfully in isolation. Split
work when data model, behavior mode, enforcement, UI, rollout, or performance
can fail independently.

Use an explicit dependency graph rather than relying on priority order. Priority
chooses among eligible tasks; it does not override dependencies.

## Inventory and reuse

Before creating tasks, inspect existing modules, parsers, schedulers, caches,
configuration, pages, tests, CI, and prior task systems. Every task records:

- the existing owner to extend
- responsibilities that must not be duplicated
- a stable fingerprint for overlap detection
- a decision: reuse, amend, supersede, or justified creation

Path overlap is a warning, not automatic duplication; identical responsibility
fingerprints are an error until deliberately resolved.

## Verification design

Every acceptance criterion maps to one or more checks. Checks use argv arrays,
not shell prose, and include a cwd and timeout.

Test checks must declare a minimum discovery count of at least one. Language and
platform variants are first-class:

- Go: build tags, race, fuzz duration, benchmark and allocation limits
- Rust: features/all-features and target configuration
- JVM/.NET: test filters, build configuration, target framework
- frontend: exact test files/names, typecheck, lint, and production build
- UI/manual: explicit steps and artifact references; never masquerade as tests

Performance criteria use numbers and a recorded baseline. Phrases such as "no
unacceptable regression" are not verifiable.

## State machine

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

A blocker includes a reason code, evidence, and the action required to unblock.
A source, dependency, definition, or verification change that invalidates an
old pass produces `regressed`.

## Independent review

Specification review happens before revision 1 is frozen. Completion review
happens after each evidence attempt. Independence requires both a different actor identity and a different session,
with concrete non-placeholder identities stored in the review record.
The reviewer checks actual files and evidence rather than repeating the
implementer's summary.

## Authorization boundaries

A project template cannot authorize side effects. Inventory/read-only analysis,
local edits, dependency installation, commit, push, deployment, and production
access are separate operations governed by the user's current request and the
active permission mode. `init.sh` stays read-only and never installs, edits,
commits, pushes, or repairs state.

## Legacy migration

Migrate old manifests conservatively:

- `passes: false` becomes `status: ready` unless a known blocker is recorded
- `passes: true` becomes `awaiting_review` with a legacy claim unless accepted
  through an explicit attestation policy
- add definition revisions, dependencies, targets, criteria, and executable
  verification
- independently audit paths, commands, test discovery, and reuse before work
- never fabricate evidence for historical claims

The compatibility field can be removed only in a future major schema version.
